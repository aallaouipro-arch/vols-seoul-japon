"""Alertes de prix sur n'importe quel vol.

Une alerte = un trajet + des dates (ou plusieurs dates possibles : « dates flexibles »).
Elle appartient à un appareil, ou est **partagée** (visible et notifiée sur tous les
appareils : utilisé pour le voyage commun de l'utilisateur et de son ami).
"""

import logging
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from itertools import product

from .bags import BAG_INCLUDED_CARRIERS, bag_cost
from .gflights import GoogleFlights, Offer, search_with_bags
from .links import booking_url
from .store import Store
from .webpush import broadcast, send

log = logging.getLogger("tracker")

HISTORY_MAX = 400  # points de prix gardés par alerte
SHARED = "shared"  # « appareil » des alertes partagées


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def offer_dict(o: Offer, bags: list[int], bag_links: dict | None = None) -> dict:
    fee, note = bag_cost(o.airlines, o.duration_min, bags, o.airline_code) if any(bags) else (0, "")
    return {
        "bag_policy_url": (bag_links or {}).get(o.airline_code),
        "price": o.price,
        "bag_fee": fee,
        "bag_note": note,
        "total": o.price + fee,
        "airlines": o.airlines,
        "airline_code": o.airline_code,
        "route": o.route,
        "depart": o.depart,
        "arrive": o.arrive,
        "duration_min": o.duration_min,
        "stops": o.stops,
        "layovers": [{"code": c, "minutes": m, "city": city} for c, m, city in o.layovers],
        "segments": [list(s) for s in o.segments],
    }


def date_pairs(w: dict) -> list[tuple[str, str | None]]:
    """Toutes les combinaisons de dates à tester (aller, retour)."""
    departs = w.get("depart_options") or [w["depart"]]
    rets = w.get("ret_options") or ([w["ret"]] if w.get("ret") else [None])
    today = date.today().isoformat()
    return [(d, r) for d, r in product(departs, rets) if d >= today and (r is None or r > d)]


def bags_of(w: dict) -> list[int]:
    return [w.get("bags_out", 0)] + ([w.get("bags_ret", 0)] if w.get("ret") else [])


def _total(o: Offer, bags: list[int]) -> int:
    return o.price + (bag_cost(o.airlines, o.duration_min, bags, o.airline_code)[0] if any(bags) else 0)


# --- CRUD ---

def create(store: Store, device: str, data: dict) -> dict:
    w = {
        "id": secrets.token_hex(5),
        "device": device,
        "shared": device == SHARED,
        "origin": data["origin"],
        "destination": data["destination"],
        "origin_label": data.get("origin_label") or data["origin"],
        "destination_label": data.get("destination_label") or data["destination"],
        "depart": data["depart"],
        "ret": data.get("ret") or None,
        "depart_options": data.get("depart_options") or None,
        "ret_options": data.get("ret_options") or None,
        "note": data.get("note"),
        "stops": data.get("stops", 1),
        "bags_out": int(data.get("bags_out", 0)),
        "bags_ret": int(data.get("bags_ret", 0)),
        "target": int(data["target"]) if data.get("target") else None,
        "created": now_iso(),
        "last_price": data.get("current_price"),
        "min_price": data.get("current_price"),
        "level": None,
        "last_check": None,
        "notified_price": None,
    }
    store.set(f"watch:{w['id']}", w)
    store.sadd("watches", w["id"])
    store.sadd(f"device:{device}:watches", w["id"])
    if w["last_price"]:
        store.push_capped(f"hist:{w['id']}", [now_iso(), w["last_price"]], HISTORY_MAX)
    return w


def list_for(store: Store, device: str) -> list[dict]:
    ids = store.smembers(f"device:{SHARED}:watches") + store.smembers(f"device:{device}:watches")
    out = [store.get(f"watch:{i}") for i in dict.fromkeys(ids)]
    return sorted((w for w in out if w), key=lambda w: (not w.get("shared"), w["depart"]))


def delete(store: Store, device: str, watch_id: str) -> bool:
    w = store.get(f"watch:{watch_id}")
    if not w or w["device"] != device:  # une alerte partagée ne se supprime pas depuis l'appli
        return False
    store.delete(f"watch:{watch_id}")
    store.delete(f"hist:{watch_id}")
    store.srem("watches", watch_id)
    store.srem(f"device:{device}:watches", watch_id)
    return True


def history(store: Store, watch_id: str) -> list:
    return store.lrange(f"hist:{watch_id}")


# --- Vérification périodique ---

def _search_pair(w: dict, pair: tuple[str, str | None]):
    d, r = pair
    legs = [(d, w["origin"], w["destination"])] + ([(r, w["destination"], w["origin"])] if r else [])
    try:
        return pair, search_with_bags(legs, w.get("stops", 1), BAG_INCLUDED_CARRIERS, any(bags_of(w)))
    except Exception as e:
        log.warning("Alerte %s %s : %s", w["id"], pair, e)
        return pair, None


def check(store: Store, w: dict, gf: GoogleFlights | None = None) -> dict | None:
    """Relève le meilleur prix d'une alerte (toutes ses dates), l'enregistre et notifie si besoin."""
    pairs = date_pairs(w)
    if not pairs:
        return None  # dates passées : plus de suivi
    with ThreadPoolExecutor(max_workers=min(9, len(pairs))) as ex:
        results = [(p, r) for p, r in ex.map(lambda p: _search_pair(w, p), pairs) if r and r.offers]
    w["last_check"] = now_iso()
    if not results:
        store.set(f"watch:{w['id']}", w)
        return None

    bags = bags_of(w)
    price, best, (dep, ret), res = min(
        ((_total(o, bags), o, p, r) for p, r in results for o in r.offers), key=lambda t: t[0]
    )
    ins = res.insights
    level = ins.level if ins else None

    # Aller-retour : retour le moins cher pour cet aller → lien de réservation du billet exact
    book, ret_flight = None, None
    try:
        if ret:
            legs = [(dep, w["origin"], w["destination"]), (ret, w["destination"], w["origin"])]
            rets = (gf or GoogleFlights()).search_returns(legs, best.segments, w.get("stops", 1)).offers
            if rets:
                r_best = min(rets, key=lambda o: o.price)
                book = booking_url(best.segments, r_best.segments)
                ret_flight = f"{r_best.depart[-5:]} · {', '.join(r_best.airlines)}"
        else:
            book = booking_url(best.segments)
    except Exception as e:
        log.warning("Lien de réservation %s : %s", w["id"], e)

    prev, prev_level, prev_min = w.get("last_price"), w.get("level"), w.get("min_price")
    route = f"{w['origin_label']} ⇄ {w['destination_label']}" if w.get("ret") else f"{w['origin_label']} → {w['destination_label']}"
    when = f"{dep[8:10]}/{dep[5:7]}" + (f" → {ret[8:10]}/{ret[5:7]}" if ret else "")
    who = ", ".join(best.airlines)
    event = None
    if w.get("target") and price <= w["target"] and (w.get("notified_price") is None or price < w["notified_price"]):
        event = ("🎯 Prix cible atteint", f"{route} : {price} € (cible {w['target']} €) · {when} · {who}")
    elif prev_min and price <= prev_min - 5 and w.get("last_check_count", 0) > 0:
        event = ("🏆 Plus bas jamais vu", f"{route} : {price} € (avant {prev_min} €) · {when} · {who}")
    elif prev and prev - price >= max(10, prev * 0.03):
        event = ("📉 Le prix baisse", f"{route} : {price} € au lieu de {prev} € · {when} · {who}")
    elif level == "bas" and prev_level not in (None, "bas"):
        event = ("🔥 Prix bas", f"{route} : {price} €, sous le prix habituel selon Google Flights · {when}")

    fee = price - best.price
    w.update(
        last_price=price,
        fare=best.price,
        bag_fee=fee,
        min_price=min(price, prev_min or price),
        level=level,
        typical_low=ins.typical_low if ins else None,
        typical_high=ins.typical_high if ins else None,
        airline=who,
        airline_code=best.airline_code,
        bag_note=bag_cost(best.airlines, best.duration_min, bags, best.airline_code)[1] if any(bags) else None,
        bag_policy_url=res.bag_links.get(best.airline_code),
        stops_found=best.stops,
        best_depart=dep,
        best_ret=ret,
        depart_time=best.depart[-5:],
        return_flight=ret_flight,
        google_url=res.url,
        booking_url=book,
        last_check_count=w.get("last_check_count", 0) + 1,
    )
    if event:
        w["notified_price"] = price
    store.set(f"watch:{w['id']}", w)
    store.push_capped(f"hist:{w['id']}", [w["last_check"], price], HISTORY_MAX)
    if event:
        url, tag = f"/#/alertes/{w['id']}", f"watch-{w['id']}"
        if w.get("shared"):
            broadcast(store, event[0], event[1], url=url, tag=tag)
        else:
            send(store, w["device"], event[0], event[1], url=url, tag=tag)
        log.info("Alerte %s : %s", w["id"], event[1])
    return {"title": event[0], "body": event[1]} if event else None


def check_due(store: Store, budget_s: float = 45) -> dict:
    """Vérifie les alertes, les plus anciennement vérifiées d'abord, dans la limite de temps."""
    start = time.monotonic()
    watches = [store.get(f"watch:{i}") for i in store.smembers("watches")]
    watches = sorted((w for w in watches if w), key=lambda w: w.get("last_check") or "")
    done, events, errors = 0, [], 0
    for w in watches:
        if time.monotonic() - start > budget_s:
            break
        try:
            ev = check(store, w)
            done += 1
            if ev:
                events.append(ev)
        except Exception as e:
            errors += 1
            log.warning("Alerte %s en échec : %s", w.get("id"), e)
    return {"checked": done, "total": len(watches), "events": events, "errors": errors}
