"""API de l'appli Google Tracker (fonction Python Vercel, région Paris).

En local : uvicorn api.index:app --port 8000
"""

import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Header, HTTPException, Query  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from tracker import alerts, webpush  # noqa: E402
from tracker.gflights import GoogleFlights, GoogleFlightsError  # noqa: E402
from tracker.links import booking_url, partner_links  # noqa: E402
from tracker.store import get_store  # noqa: E402

app = FastAPI(title="Google Tracker", docs_url="/api/docs", openapi_url="/api/openapi.json")

CODE_RE = re.compile(r"^[A-Z]{3}(\+[A-Z]{3}){0,3}$")
DEVICE_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
TRIP_JSON_URL = os.environ.get("TRIP_JSON_URL", "https://aallaouipro-arch.github.io/vols-seoul-japon/trip.json")


# --- Validation ---

def _code(v: str) -> str:
    v = (v or "").upper().replace(" ", "+")
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


# --- Recherche ---

@app.get("/api/health")
def health():
    return {"ok": True, "store": type(get_store()).__name__}


@app.get("/api/config")
def config():
    return {"vapid_public_key": webpush.public_key()}


@app.get("/api/search")
def search(
    origin: str, destination: str, depart: str, ret: str | None = None,
    stops: str = "1", bags_out: int = Query(0, ge=0, le=3), bags_ret: int = Query(0, ge=0, le=3),
):
    o, d = _code(origin), _code(destination)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    if ret and ret < depart:
        raise HTTPException(400, "Le retour doit être après l'aller")
    legs = [(depart, o, d)] + ([(ret, d, o)] if ret else [])
    bags = [bags_out] + ([bags_ret] if ret else [])
    res = _search(lambda: GoogleFlights().search(legs, _stops(stops)))
    offers = []
    for off in res.offers:
        item = alerts.offer_dict(off, bags)
        if not ret:
            item["booking_url"] = booking_url(off.segments)
        offers.append(item)
    offers.sort(key=lambda x: x["total"])
    ins = res.insights
    return {
        "query": {"origin": o, "destination": d, "depart": depart, "ret": ret, "stops": stops, "bags": bags},
        "offers": offers,
        "insights": {
            "current": ins.current, "typical_low": ins.typical_low, "typical_high": ins.typical_high,
            "level": ins.level, "history": ins.history,
        } if ins else None,
        "google_url": res.url,
        "links": partner_links(o, d, depart, ret),
    }


@app.get("/api/returns")
def returns(
    origin: str, destination: str, depart: str, ret: str, out: str,
    stops: str = "1", bags_out: int = Query(0, ge=0, le=3), bags_ret: int = Query(0, ge=0, le=3),
):
    """Aller-retour : vols retour possibles pour l'aller choisi (`out` = segments JSON)."""
    o, d = _code(origin), _code(destination)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    try:
        out_segments = [tuple(s) for s in json.loads(out)]
        assert out_segments and all(len(s) == 5 for s in out_segments)
    except Exception:
        raise HTTPException(400, "Vol aller invalide")
    res = _search(lambda: GoogleFlights().search_returns([(depart, o, d), (ret, d, o)], out_segments, _stops(stops)))
    offers = []
    for off in res.offers:
        item = alerts.offer_dict(off, [bags_out, bags_ret])  # prix = total de l'aller-retour
        item["booking_url"] = booking_url(out_segments, off.segments)
        offers.append(item)
    offers.sort(key=lambda x: x["total"])
    return {"offers": offers, "google_url": res.url}


@app.get("/api/flex")
def flex(origin: str, destination: str, depart: str, ret: str | None = None, stops: str = "1", days: int = Query(3, ge=1, le=3)):
    """Prix le plus bas en décalant les dates de ±days jours (même durée de séjour)."""
    o, d = _code(origin), _code(destination)
    depart, ret = _date(depart, "de départ"), _date(ret, "de retour")
    stay = (date.fromisoformat(ret) - date.fromisoformat(depart)).days if ret else None
    shifts = [k for k in range(-days, days + 1) if date.fromisoformat(depart) + timedelta(days=k) >= date.today()]

    def one(k):
        dd = (date.fromisoformat(depart) + timedelta(days=k)).isoformat()
        rr = (date.fromisoformat(dd) + timedelta(days=stay)).isoformat() if stay is not None else None
        try:
            best = GoogleFlights().search([(dd, o, d)] + ([(rr, d, o)] if rr else []), _stops(stops)).best
            return {"depart": dd, "ret": rr, "price": best.price if best else None}
        except Exception:
            return {"depart": dd, "ret": rr, "price": None}

    with ThreadPoolExecutor(max_workers=7) as ex:
        return {"days": list(ex.map(one, shifts))}


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
    if not w or w["device"] != _device(device):
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
