"""API de l'appli Google Tracker (fonction Python Vercel, région Paris).

En local : uvicorn api.index:app --port 8000
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from tracker import alerts, deals, webpush  # noqa: E402
from tracker.bags import BAG_INCLUDED_CARRIERS  # noqa: E402
from tracker.gflights import (  # noqa: E402
    GoogleFlights, GoogleFlightsError, SearchOptions, deep_search, full_search, is_place_id, multicity_url,
    search_with_bags, suggest_places,
)
from tracker.links import booking_url, partner_links  # noqa: E402
from tracker.store import get_store  # noqa: E402

app = FastAPI(title="Google Tracker", docs_url="/api/docs", openapi_url="/api/openapi.json")

CODE_RE = re.compile(r"^[A-Z]{3}(\+[A-Z]{3}){0,3}$")
DEVICE_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
TRIP_JSON_URL = os.environ.get("TRIP_JSON_URL", "https://aallaouipro-arch.github.io/vols-seoul-japon/trip.json")
FULL_LIST_URL = os.environ.get("FULL_LIST_URL")  # sinon https://<domaine de l'appli>/api/full (Vercel)


# --- Validation ---

def _code(v: str) -> str:
    """Code IATA (ou plusieurs séparés par +), ou lieu Google (pays, ville… ex. /m/03_3d)."""
    v = (v or "").strip()
    if is_place_id(v):
        return v
    v = v.upper().replace(" ", "+")
    if not CODE_RE.match(v):
        raise HTTPException(400, f"Code aéroport invalide : {v}")
    return v


def _date(v: str | None, name: str) -> str | None:
    if not v:
        return None
    try:
        d = date.fromisoformat(v)
    except ValueError:
        raise HTTPException(400, f"Date invalide ({name}) : {v}")
    if d < date.today():
        raise HTTPException(400, f"La date {name} est passée")
    return v


def _stops(v: str) -> int | None:
    return {"0": 0, "1": 1, "2": 2}.get(v)  # "any" → None (illimité)


def _device(v: str) -> str:
    if not DEVICE_RE.match(v or ""):
        raise HTTPException(400, "Identifiant d'appareil invalide")
    return v


def _secret(authorization: str | None):
    expected = os.environ.get("CRON_SECRET")
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, "Non autorisé")


def _search(fn):
    try:
        return fn()
    except GoogleFlightsError as e:
        raise HTTPException(502, f"Google Flights : {e}")


# --- Options communes de recherche (passagers, classe, escales) ---

def search_opts(
    stops: str = "1",
    cabin: str = "economy",
    adults: int = Query(1, ge=1, le=9),
    children: int = Query(0, ge=0, le=8),
    infants_seat: int = Query(0, ge=0, le=4),
    infants_lap: int = Query(0, ge=0, le=4),
) -> SearchOptions:
    if adults + children + infants_seat + infants_lap > 9:
        raise HTTPException(400, "9 passagers maximum")
    if infants_lap > adults:
        raise HTTPException(400, "Un bébé sur les genoux par adulte maximum")
    if cabin not in SearchOptions.SEATS:
        raise HTTPException(400, "Classe inconnue")
    return SearchOptions(adults=adults, children=children, infants_seat=infants_seat, infants_lap=infants_lap,
                         seat=cabin, max_stops=_stops(stops))


def _opts_key(o: SearchOptions) -> str:
    return f"{o.adults}.{o.children}.{o.infants_seat}.{o.infants_lap}.{o.seat}.{o.max_stops}"


def _cache_key(*parts) -> str:
    return "cache:" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()


def _cached(key: str, ttl: int, fn, keep_last_good: bool = True):
    """Cache (Redis) : résultat frais pendant `ttl` s. Si Google tombe en panne, on renvoie le
    dernier résultat valide (24 h) en le marquant `stale` plutôt qu'une erreur."""
    store = get_store()
    try:
        hit = store.get(key)
    except Exception:
        hit = None
    if hit is not None:
        return hit
    try:
        data = fn()
    except (GoogleFlightsError, HTTPException) as e:
        last = store.get(key + ":good") if keep_last_good else None
        if last is not None:
            return {**last, "stale": True, "stale_reason": str(getattr(e, "detail", e))}
        raise
    data["fetched_at"] = alerts.now_iso()
    ttl = data.pop("_ttl", ttl)
    try:
        store.set(key, data, ex=ttl)
        if keep_last_good:
            store.set(key + ":good", data, ex=24 * 3600)
    except Exception:
        pass
    return data


# --- Recherche ---

@app.get("/api/health")
def health():
    store = get_store()
    try:
        h = store.get("health") or {}
    except Exception as e:
        return {"ok": False, "store": type(store).__name__, "error": str(e)}
    return {"ok": h.get("ok", True), "store": type(store).__name__, "last_check": h.get("at"), "error": h.get("error")}


def _links(o: str, d: str, depart: str, ret: str | None, pax: int, offers) -> dict:
    """Liens Trip.com / Kayak / Skyscanner. Pour un pays ou une ville sans code IATA, on prend les
    aéroports du vol le moins cher trouvé."""
    if is_place_id(o) or is_place_id(d):
        best = min(offers, key=lambda x: x.price, default=None)
        if best is None:
            return {}
        route = best.route.split("-")
        o = route[0] if is_place_id(o) else o
        d = route[-1] if is_place_id(d) else d
    return partner_links(o, d, depart, ret, pax)


@app.get("/api/places")
def places(q: str = Query(..., min_length=1, max_length=60)):
    """Autocomplétion de Google Flights : pays, régions, villes (avec aéroports proches), aéroports."""
    key = q.strip().lower()
    return _cached(_cache_key("places", key), 7 * 24 * 3600, lambda: {"places": _search(lambda: suggest_places(key))},
                   keep_last_good=False)


@app.get("/api/config")
def config():
    return {"vapid_public_key": webpush.public_key()}


def _full_list_fetcher(request: Request):
    """Appel de la fonction navigateur api/full.js (liste complète de Google), ou None si indisponible."""
    secret = os.environ.get("CRON_SECRET")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    url = FULL_LIST_URL or (f"https://{host}/api/full" if host and os.environ.get("VERCEL") else None)
    if not secret or not url:
        return None

    def fetch(tfs: str) -> str | None:
        req = urllib.request.Request(f"{url}?{urlencode({'tfs': tfs})}", headers={"Authorization": f"Bearer {secret}"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            raise GoogleFlightsError(f"navigateur : {e.read()[:200].decode(errors='replace')}")
        return data.get("payload")

    return fetch


@app.get("/api/search")
def search(
    request: Request,
    origin: str, destination: str, depart: str, ret: str | None = None,
    bags_out: int = Query(0, ge=0, le=3), bags_ret: int = Query(0, ge=0, le=3),
    deep: bool = False, opts: SearchOptions = Depends(search_opts),
):
    """Recherche en direct. deep=true : « Afficher plus de vols » = liste complète de Google (vrai
    navigateur, api/full.js) ; à défaut, recherche découpée (tranches horaires, alliances…)."""
    o, d = _code(origin), _code(destination)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    if ret and ret < depart:
        raise HTTPException(400, "Le retour doit être après l'aller")
    legs = [(depart, o, d)] + ([(ret, d, o)] if ret else [])
    bags = [bags_out] + ([bags_ret] if ret else [])
    fetch_full = _full_list_fetcher(request) if deep else None

    def fetch():
        full, unpriced, full_error = False, 0, None
        if deep:
            res = None
            if fetch_full:
                try:
                    res, unpriced = full_search(legs, opts, fetch_full)
                    full = True
                except Exception as e:  # navigateur refusé ou trop lent : recherche découpée
                    full_error = str(e)[:200]
            if res is None:
                res = _search(lambda: deep_search(legs, opts, BAG_INCLUDED_CARRIERS if any(bags) else None))
        else:
            res = _search(lambda: search_with_bags(legs, -1, BAG_INCLUDED_CARRIERS, any(bags), opts))
        offers = []
        for off in res.offers:
            item = alerts.offer_dict(off, bags, res.bag_links, opts.travelers_with_bags)
            if not ret:
                item["booking_url"] = booking_url(off.segments)
            offers.append(item)
        offers.sort(key=lambda x: x["total"])
        ins = res.insights
        return {
            "query": {"origin": o, "destination": d, "depart": depart, "ret": ret, "bags": bags, "deep": deep,
                      "full": full, "unpriced": unpriced, "full_error": full_error},
            "offers": offers,
            "insights": {
                "current": ins.current, "typical_low": ins.typical_low, "typical_high": ins.typical_high,
                "level": ins.level, "history": ins.history,
            } if ins else None,
            "google_url": res.url,
            "links": _links(o, d, depart, ret, opts.adults + opts.children, res.offers),
            **({"_ttl": 60} if deep and not full else {}),  # repli : on retentera vite la liste complète
        }

    return _cached(_cache_key("search", o, d, depart, ret, bags, deep, _opts_key(opts)), 600, fetch)


@app.get("/api/returns")
def returns(
    origin: str, destination: str, depart: str, ret: str, out: str,
    bags_out: int = Query(0, ge=0, le=3), bags_ret: int = Query(0, ge=0, le=3),
    opts: SearchOptions = Depends(search_opts),
):
    """Aller-retour : vols retour possibles pour l'aller choisi (`out` = segments JSON)."""
    o, d = _code(origin), _code(destination)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    try:
        out_segments = [tuple(s) for s in json.loads(out)]
        assert out_segments and all(len(s) == 5 for s in out_segments)
    except Exception:
        raise HTTPException(400, "Vol aller invalide")
    res = _search(lambda: GoogleFlights().search_returns([(depart, o, d), (ret, d, o)], out_segments, opts=opts))
    offers = []
    for off in res.offers:
        item = alerts.offer_dict(off, [bags_out, bags_ret], res.bag_links, opts.travelers_with_bags)  # prix = total A/R
        item["booking_url"] = booking_url(out_segments, off.segments)
        offers.append(item)
    offers.sort(key=lambda x: x["total"])
    return {"offers": offers, "google_url": res.url}


def _best_price(legs, opts):
    try:
        best = GoogleFlights().search(legs, opts=opts).best
        return best.price if best else None
    except Exception:
        return None


@app.get("/api/flex")
def flex(origin: str, destination: str, depart: str, ret: str | None = None, days: int = Query(3, ge=1, le=3),
         opts: SearchOptions = Depends(search_opts)):
    """Prix le plus bas en décalant les dates de ±days jours (même durée de séjour)."""
    o, d = _code(origin), _code(destination)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    stay = (date.fromisoformat(ret) - date.fromisoformat(depart)).days if ret else None
    shifts = [k for k in range(-days, days + 1) if date.fromisoformat(depart) + timedelta(days=k) >= date.today()]

    def one(k):
        dd = (date.fromisoformat(depart) + timedelta(days=k)).isoformat()
        rr = (date.fromisoformat(dd) + timedelta(days=stay)).isoformat() if stay is not None else None
        return {"depart": dd, "ret": rr, "price": _best_price([(dd, o, d)] + ([(rr, d, o)] if rr else []), opts)}

    def fetch():
        with ThreadPoolExecutor(max_workers=7) as ex:
            return {"days": list(ex.map(one, shifts))}

    return _cached(_cache_key("flex", o, d, depart, ret, days, _opts_key(opts)), 1800, fetch)


@app.get("/api/calendar")
def calendar(origin: str, destination: str, start: str, days: int = Query(30, ge=7, le=35),
             stay: int | None = Query(None, ge=1, le=60), opts: SearchOptions = Depends(search_opts)):
    """Calendrier / graphique des prix : prix le plus bas pour chaque date de départ sur `days` jours
    (séjour de `stay` jours si aller-retour)."""
    o, d = _code(origin), _code(destination)
    start = _date(start, "de début")
    dates = [(date.fromisoformat(start) + timedelta(days=k)).isoformat() for k in range(days)]

    def one(dd):
        rr = (date.fromisoformat(dd) + timedelta(days=stay)).isoformat() if stay else None
        return {"depart": dd, "ret": rr, "price": _best_price([(dd, o, d)] + ([(rr, d, o)] if rr else []), opts)}

    def fetch():
        with ThreadPoolExecutor(max_workers=12) as ex:
            out = list(ex.map(one, dates))
        prices = [x["price"] for x in out if x["price"]]
        return {"days": out, "min": min(prices, default=None), "max": max(prices, default=None)}

    return _cached(_cache_key("calendar", o, d, start, days, stay, _opts_key(opts)), 6 * 3600, fetch)


@app.get("/api/explore")
def explore(origin: str = "CDG+ORY", depart: str = "", ret: str | None = None, opts: SearchOptions = Depends(search_opts)):
    """Explorer : meilleur prix vers ~85 destinations pour ces dates (comme la carte Google Flights)."""
    o = _code(origin)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    if not depart:
        raise HTTPException(400, "Date de départ requise")

    def fetch():
        return {"origin": o, "depart": depart, "ret": ret, "items": deals.explore(o, depart, ret, opts)}

    return _cached(_cache_key("explore", o, depart, ret, _opts_key(opts)), 6 * 3600, fetch)


class LegIn(BaseModel):
    origin: str
    destination: str
    date: str
    bags: int = Field(0, ge=0, le=3)


class MultiIn(BaseModel):
    legs: list[LegIn] = Field(..., min_length=2, max_length=5)
    stops: str = "1"
    cabin: str = "economy"
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=8)


@app.post("/api/multi")
def multi(body: MultiIn):
    """Multi-destinations : chaque trajet en billet séparé (meilleures options + liens de réservation)
    et lien Google Flights pour comparer avec un billet unique."""
    opts = search_opts(body.stops, body.cabin, body.adults, body.children, 0, 0)
    legs = [(_date(l.date, f"du trajet {i + 1}"), _code(l.origin), _code(l.destination)) for i, l in enumerate(body.legs)]
    if any(legs[i][0] > legs[i + 1][0] for i in range(len(legs) - 1)):
        raise HTTPException(400, "Les trajets doivent être dans l'ordre chronologique")

    def one(i):
        d, o, dst = legs[i]
        bags = [body.legs[i].bags]
        res = search_with_bags([(d, o, dst)], -1, BAG_INCLUDED_CARRIERS, any(bags), opts)
        offers = []
        for off in res.offers:
            item = alerts.offer_dict(off, bags, res.bag_links, opts.travelers_with_bags)
            item["booking_url"] = booking_url(off.segments)
            offers.append(item)
        offers.sort(key=lambda x: x["total"])
        return {"origin": o, "destination": dst, "date": d, "offers": offers[:15], "google_url": res.url,
                "links": _links(o, dst, d, None, opts.adults + opts.children, res.offers)}

    with ThreadPoolExecutor(max_workers=5) as ex:
        out = list(ex.map(lambda i: _search(lambda: one(i)), range(len(legs))))
    total = sum(l["offers"][0]["total"] for l in out if l["offers"]) if all(l["offers"] for l in out) else None
    return {"legs": out, "total_separate": total, "google_multicity_url": multicity_url(legs, opts)}


# --- Alertes ---

class WatchIn(BaseModel):
    device: str
    origin: str
    destination: str
    origin_label: str | None = None
    destination_label: str | None = None
    depart: str
    ret: str | None = None
    stops: int | None = 1
    bags_out: int = Field(0, ge=0, le=3)
    bags_ret: int = Field(0, ge=0, le=3)
    target: int | None = Field(None, ge=1)
    current_price: int | None = None


@app.get("/api/watches")
def list_watches(device: str):
    return {"watches": alerts.list_for(get_store(), _device(device))}


@app.post("/api/watches")
def create_watch(body: WatchIn):
    data = body.model_dump()
    data["origin"], data["destination"] = _code(body.origin), _code(body.destination)
    _date(body.depart, "de départ"), _date(body.ret, "de retour")
    store = get_store()
    if len(store.smembers(f"device:{_device(body.device)}:watches")) >= 30:
        raise HTTPException(400, "30 alertes maximum par appareil")
    w = alerts.create(store, body.device, data)
    try:  # premier relevé tout de suite (fourchette habituelle, compagnie, lien de réservation)
        alerts.check(store, w)
    except Exception:
        pass  # le passage horaire s'en chargera
    return store.get(f"watch:{w['id']}") or w


class SharedWatchIn(WatchIn):
    device: str = alerts.SHARED
    depart_options: list[str] | None = None
    ret_options: list[str] | None = None
    note: str | None = None


@app.post("/api/watches/shared")
def create_shared_watch(body: SharedWatchIn, authorization: str | None = Header(None)):
    """Alerte partagée : visible et notifiée sur tous les appareils (réservé à l'administrateur)."""
    _secret(authorization)
    data = body.model_dump()
    data["origin"], data["destination"] = _code(body.origin), _code(body.destination)
    for d in [body.depart, body.ret, *(body.depart_options or []), *(body.ret_options or [])]:
        _date(d, "")
    store = get_store()
    w = alerts.create(store, alerts.SHARED, data)
    _search(lambda: alerts.check(store, w))
    return store.get(f"watch:{w['id']}")


@app.delete("/api/watches/{watch_id}")
def delete_watch(watch_id: str, device: str):
    if not alerts.delete(get_store(), _device(device), watch_id):
        raise HTTPException(404, "Alerte introuvable")
    return {"ok": True}


@app.get("/api/watches/{watch_id}/history")
def watch_history(watch_id: str):
    return {"history": alerts.history(get_store(), watch_id)}


@app.post("/api/watches/{watch_id}/check")
def check_watch(watch_id: str, device: str):
    store = get_store()
    w = store.get(f"watch:{watch_id}")
    if not w or (w["device"] != _device(device) and not w.get("shared")):
        raise HTTPException(404, "Alerte introuvable")
    _search(lambda: alerts.check(store, w))
    return store.get(f"watch:{watch_id}")


# --- Notifications ---

class SubscribeIn(BaseModel):
    device: str
    subscription: dict


@app.post("/api/push/subscribe")
def subscribe(body: SubscribeIn):
    if not body.subscription.get("endpoint", "").startswith("https://"):
        raise HTTPException(400, "Abonnement invalide")
    webpush.save_subscription(get_store(), _device(body.device), body.subscription)
    return {"ok": True}


@app.post("/api/push/test")
def push_test(device: str):
    n = webpush.send(get_store(), _device(device), "✈️ Google Tracker", "Les notifications fonctionnent !", "/")
    return {"sent": n}


class BroadcastIn(BaseModel):
    title: str
    body: str
    url: str = "/"
    tag: str | None = None


@app.post("/api/broadcast")
def broadcast(body: BroadcastIn, authorization: str | None = Header(None)):
    """Notification à tous les appareils (alertes du voyage, envoyées par le tracker GitHub)."""
    _secret(authorization)
    return {"sent": webpush.broadcast(get_store(), body.title, body.body, body.url, body.tag)}


@app.api_route("/api/cron/check", methods=["GET", "POST"])
def cron_check(authorization: str | None = Header(None)):
    _secret(authorization)
    return alerts.check_due(get_store())


# --- Bons plans (scan quotidien, notification hebdomadaire) ---

@app.get("/api/deals")
def get_deals():
    return get_store().get("deals") or {"items": [], "generated_at": None}


@app.api_route("/api/cron/deals", methods=["GET", "POST"])
def cron_deals(notify: bool = False, authorization: str | None = Header(None)):
    _secret(authorization)
    store = get_store()
    data = deals.scan()
    deals.save(store, data)
    sent = 0
    if notify and (msg := deals.summary(data)):
        sent = webpush.broadcast(store, msg[0], msg[1], url="/", tag="deals")
    return {"checked": data["checked"], "destinations": len(data["items"]),
            "deals": sum(i["is_deal"] for i in data["items"]), "notified": sent}


# --- Santé : détecte si Google Flights a changé (toutes les 3 h, via GitHub Actions) ---

def canary() -> tuple[bool, str]:
    """Recherche témoin Paris → Lisbonne dans 30 jours : vols, prix, segments, tendance, lien de réservation."""
    d = (date.today() + timedelta(days=30)).isoformat()
    try:
        res = GoogleFlights().search([(d, "CDG+ORY", "LIS")], opts=SearchOptions(max_stops=1))
    except Exception as e:
        return False, f"recherche impossible : {e}"
    if len(res.offers) < 3:
        return False, f"seulement {len(res.offers)} vol(s) lu(s)"
    o = res.best
    checks = {
        "prix": 20 <= o.price <= 3000,
        "segments": bool(o.segments) and all(len(s) == 5 and s[3] and s[4] for s in o.segments),
        "horaires": len(o.depart) == 16 and len(o.arrive) == 16,
        "compagnie": bool(o.airlines),
        "tendance Google": res.insights is not None and res.insights.typical_low is not None,
        "lien de réservation": booking_url(o.segments).startswith("https://www.google.com/travel/flights/booking?tfs="),
    }
    bad = [k for k, ok in checks.items() if not ok]
    return (not bad), ("OK" if not bad else "données illisibles : " + ", ".join(bad))


@app.api_route("/api/cron/health", methods=["GET", "POST"])
def cron_health(authorization: str | None = Header(None)):
    _secret(authorization)
    store = get_store()
    ok, msg = canary()
    prev = store.get("health") or {"ok": True}
    store.set("health", {"ok": ok, "at": alerts.now_iso(), "error": None if ok else msg})
    if prev.get("ok") and not ok:
        webpush.broadcast(store, "⚠️ Google Tracker en panne", f"Google Flights a peut-être changé : {msg}. Les alertes sont en pause.", "/", "health")
    elif not prev.get("ok") and ok:
        webpush.broadcast(store, "✅ Google Tracker refonctionne", "La lecture de Google Flights est rétablie.", "/", "health")
    return {"ok": ok, "message": msg}


# --- Voyage prioritaire (calculé par le tracker GitHub, 4 fois par jour) ---

_trip_cache: dict = {"at": 0.0, "data": None}


@app.get("/api/trip")
def trip():
    if time.time() - _trip_cache["at"] > 120 or _trip_cache["data"] is None:
        try:
            with urllib.request.urlopen(f"{TRIP_JSON_URL}?t={int(time.time())}", timeout=10) as r:
                _trip_cache.update(at=time.time(), data=json.loads(r.read()))
        except Exception as e:
            if _trip_cache["data"] is None:
                raise HTTPException(503, f"Données du voyage indisponibles : {e}")
    return _trip_cache["data"]
