"""Bons plans : scan régulier de destinations populaires au départ de Paris.

Pour chaque destination et quelques dates types (week-ends pour l'Europe, séjours de
10-12 jours pour le long-courrier), on relève le meilleur aller-retour et la fourchette
de prix « habituelle » de Google Flights. Un bon plan = prix sous cette fourchette
(niveau « bas ») ou au moins 20 % sous son milieu.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from .gflights import GoogleFlights
from .store import Store

log = logging.getLogger("tracker")

ORIGIN = ("CDG+ORY", "Paris")

# (code Google Flights, ville, pays ISO, région)
DESTINATIONS = [
    ("LIS", "Lisbonne", "PT", "europe"), ("OPO", "Porto", "PT", "europe"), ("BCN", "Barcelone", "ES", "europe"),
    ("MAD", "Madrid", "ES", "europe"), ("ROM", "Rome", "IT", "europe"), ("NAP", "Naples", "IT", "europe"),
    ("ATH", "Athènes", "GR", "europe"), ("LON", "Londres", "GB", "europe"), ("AMS", "Amsterdam", "NL", "europe"),
    ("BER", "Berlin", "DE", "europe"), ("PRG", "Prague", "CZ", "europe"), ("BUD", "Budapest", "HU", "europe"),
    ("VIE", "Vienne", "AT", "europe"), ("KRK", "Cracovie", "PL", "europe"), ("DUB", "Dublin", "IE", "europe"),
    ("CPH", "Copenhague", "DK", "europe"), ("RAK", "Marrakech", "MA", "europe"), ("IST", "Istanbul", "TR", "europe"),
    ("NYC", "New York", "US", "long"), ("YMQ", "Montréal", "CA", "long"), ("TYO", "Tokyo", "JP", "long"),
    ("SEL", "Séoul", "KR", "long"), ("BKK", "Bangkok", "TH", "long"), ("DPS", "Bali", "ID", "long"),
    ("DXB", "Dubaï", "AE", "long"), ("CUN", "Cancún", "MX", "long"), ("SIN", "Singapour", "SG", "long"),
    ("HAN", "Hanoï", "VN", "long"), ("MRU", "Maurice", "MU", "long"), ("RUN", "La Réunion", "RE", "long"),
    ("LAX", "Los Angeles", "US", "long"), ("RIO", "Rio de Janeiro", "BR", "long"),
]


def _next_weekday(d: date, weekday: int) -> date:
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def date_options(region: str, today: date | None = None) -> list[tuple[str, str]]:
    """Dates types relatives à aujourd'hui : (aller, retour)."""
    today = today or date.today()
    if region == "europe":  # week-ends vendredi → dimanche, dans ~3 et ~7 semaines
        out = []
        for weeks in (3, 7):
            fri = _next_weekday(today + timedelta(weeks=weeks), 4)
            out.append((fri.isoformat(), (fri + timedelta(days=2)).isoformat()))
        return out
    out = []  # long-courrier : départ mercredi dans ~6 et ~12 semaines, séjour 10 / 12 jours
    for weeks, stay in ((6, 10), (12, 12)):
        wed = _next_weekday(today + timedelta(weeks=weeks), 2)
        out.append((wed.isoformat(), (wed + timedelta(days=stay)).isoformat()))
    return out


def _check(origin: str, dest: tuple, depart: str, ret: str) -> dict | None:
    code, city, country, region = dest
    try:
        res = GoogleFlights().search([(depart, origin, code), (ret, code, origin)], 1)
    except Exception as e:
        log.warning("Bon plan %s %s : %s", code, depart, e)
        return None
    best = res.best
    if not best:
        return None
    ins = res.insights
    low, high = (ins.typical_low, ins.typical_high) if ins else (None, None)
    discount = round((1 - best.price / ((low + high) / 2)) * 100) if low and high else None
    level = ins.level if ins else None
    return {
        "code": code, "city": city, "country": country, "region": region,
        "depart": depart, "ret": ret, "price": best.price,
        "typical_low": low, "typical_high": high, "level": level, "discount": discount,
        "is_deal": level == "bas" or (discount is not None and discount >= 20),
        "airline": ", ".join(best.airlines), "airline_code": best.airline_code,
        "stops": best.stops, "duration_min": best.duration_min, "google_url": res.url,
    }


def scan(origin: str = ORIGIN[0], workers: int = 8) -> dict:
    jobs = [(d, dep, ret) for d in DESTINATIONS for dep, ret in date_options(d[3])]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = [r for r in ex.map(lambda j: _check(origin, *j), jobs) if r]
    # Une ligne par destination : la meilleure affaire (remise), sinon le prix le plus bas
    best: dict[str, dict] = {}
    for r in results:
        cur = best.get(r["code"])
        key = lambda x: (x["is_deal"], x["discount"] or -100, -x["price"])  # noqa: E731
        if cur is None or key(r) > key(cur):
            best[r["code"]] = r
    items = sorted(best.values(), key=lambda x: (not x["is_deal"], -(x["discount"] or -100), x["price"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": origin,
        "origin_label": ORIGIN[1],
        "checked": len(jobs),
        "items": items,
    }


def save(store: Store, data: dict) -> None:
    previous = store.get("deals") or {}
    seen = {(i["code"], i["depart"]) for i in previous.get("items", []) if i.get("is_deal")}
    for i in data["items"]:
        i["new"] = i["is_deal"] and (i["code"], i["depart"]) not in seen
    store.set("deals", data)


def summary(data: dict, limit: int = 3) -> tuple[str, str] | None:
    """Titre + texte de la notification hebdomadaire (None s'il n'y a aucun bon plan)."""
    deals = [i for i in data["items"] if i["is_deal"]]
    if not deals:
        return None
    top = " · ".join(f"{d['city']} {d['price']} € (-{d['discount']} %)" if d["discount"] else f"{d['city']} {d['price']} €" for d in deals[:limit])
    n = len(deals)
    return f"🔥 {n} bon{'s' if n > 1 else ''} plan{'s' if n > 1 else ''} depuis Paris cette semaine", top
