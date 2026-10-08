"""Alertes de prix sur n'importe quel vol (une alerte = un trajet + des dates, par appareil)."""

import logging
import secrets
import time
from datetime import date, datetime, timezone

from .bags import bag_cost
from .gflights import GoogleFlights, Offer
from .links import booking_url
from .store import Store
from .webpush import send

log = logging.getLogger("tracker")

HISTORY_MAX = 400  # points de prix gardés par alerte


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def offer_dict(o: Offer, bags: list[int]) -> dict:
    fee, note = bag_cost(o.airlines, o.duration_min, bags) if any(bags) else (0, "")
    return {
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


def legs_of(w: dict) -> list[tuple[str, str, str]]:
    legs = [(w["depart"], w["origin"], w["destination"])]
    if w.get("ret"):
        legs.append((w["ret"], w["destination"], w["origin"]))
    return legs


def bags_of(w: dict) -> list[int]:
    return [w.get("bags_out", 0)] + ([w.get("bags_ret", 0)] if w.get("ret") else [])


# --- CRUD ---

def create(store: Store, device: str, data: dict) -> dict:
    w = {
        "id": secrets.token_hex(5),
        "device": device,
        "origin": data["origin"],
        "destination": data["destination"],
        "origin_label": data.get("origin_label") or data["origin"],
        "destination_label": data.get("destination_label") or data["destination"],
        "depart": data["depart"],
        "ret": data.get("ret") or None,
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
    out = [store.get(f"watch:{i}") for i in store.smembers(f"device:{device}:watches")]
    return sorted((w for w in out if w), key=lambda w: w["depart"])


def delete(store: Store, device: str, watch_id: str) -> bool:
    w = store.get(f"watch:{watch_id}")
    if not w or w["device"] != device:
        return False
    store.delete(f"watch:{watch_id}")
    store.delete(f"hist:{watch_id}")
    store.srem("watches", watch_id)
    store.srem(f"device:{device}:watches", watch_id)
    return True


def history(store: Store, watch_id: str) -> list:
    return store.lrange(f"hist:{watch_id}")


# --- Vérification périodique ---

def check(store: Store, w: dict, gf: GoogleFlights | None = None) -> dict | None:
    """Relève le prix d'une alerte, l'enregistre et notifie si besoin. → événement envoyé ou None."""
    if date.fromisoformat(w["depart"]) < date.today():
        return None  # vol passé : plus de suivi
    gf = gf or GoogleFlights()
    res = gf.search(legs_of(w), w.get("stops", 1))
    w["last_check"] = now_iso()
    if not res.offers:
        store.set(f"watch:{w['id']}", w)
        return None
    bags = bags_of(w)
    priced = [(o.price + (bag_cost(o.airlines, o.duration_min, bags)[0] if any(bags) else 0), o) for o in res.offers]
    price, best = min(priced, key=lambda t: t[0])
    ins = res.insights
    level = ins.level if ins else None

    prev, prev_level = w.get("last_price"), w.get("level")
    route = f"{w['origin_label']} → {w['destination_label']}"
    event = None
    if w.get("target") and price <= w["target"] and (w.get("notified_price") is None or price < w["notified_price"]):
        event = ("🎯 Prix cible atteint", f"{route} : {price} € (cible {w['target']} €) · {', '.join(best.airlines)}")
    elif prev and prev - price >= max(10, prev * 0.03):
        event = ("📉 Le prix baisse", f"{route} : {price} € au lieu de {prev} € · {', '.join(best.airlines)}")
    elif level == "bas" and prev_level not in (None, "bas"):
        event = ("🔥 Prix bas", f"{route} : {price} €, sous le prix habituel selon Google Flights")

    w.update(
        last_price=price,
        min_price=min(price, w.get("min_price") or price),
        level=level,
        typical_low=ins.typical_low if ins else None,
        typical_high=ins.typical_high if ins else None,
        airline=", ".join(best.airlines),
        airline_code=best.airline_code,
        google_url=res.url,
        booking_url=booking_url(best.segments) if not w.get("ret") else None,
    )
    if event:
        w["notified_price"] = price
    store.set(f"watch:{w['id']}", w)
    store.push_capped(f"hist:{w['id']}", [w["last_check"], price], HISTORY_MAX)
    if event:
        send(store, w["device"], event[0], event[1], url=f"/#/alertes/{w['id']}", tag=f"watch-{w['id']}")
        log.info("Alerte %s : %s", w["id"], event[1])
    return {"title": event[0], "body": event[1]} if event else None


def check_due(store: Store, budget_s: float = 45) -> dict:
    """Vérifie les alertes, les plus anciennement vérifiées d'abord, dans la limite de temps."""
    start = time.monotonic()
    watches = [store.get(f"watch:{i}") for i in store.smembers("watches")]
    watches = sorted((w for w in watches if w), key=lambda w: w.get("last_check") or "")
    gf = GoogleFlights()
    done, events, errors = 0, [], 0
    for w in watches:
        if time.monotonic() - start > budget_s:
            break
        try:
            ev = check(store, w, gf)
            done += 1
            if ev:
                events.append(ev)
        except Exception as e:
            errors += 1
            log.warning("Alerte %s en échec : %s", w.get("id"), e)
    return {"checked": done, "total": len(watches), "events": events, "errors": errors}
