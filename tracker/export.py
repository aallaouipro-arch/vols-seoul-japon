"""Export site/trip.json : données du voyage prioritaire pour l'appli Google Tracker
(publié avec le site GitHub Pages à chaque relevé)."""

import json

from .links import partner_links
from .plan import STRATEGIES


def _leg(l: dict) -> dict:
    q = l.get("query") or []
    links = {}
    if q:
        origin, destination = q[0][1], q[0][2]
        links = partner_links(origin, destination, q[0][0], q[1][0] if len(q) > 1 else None)
    return {
        "search": l["search"],
        "origin": q[0][1] if q else None,
        "destination": q[0][2] if q else None,
        "depart_date": q[0][0] if q else None,
        "return_date": q[1][0] if len(q) > 1 else None,
        "total": l["price"],
        "fare": l["fare"],
        "bag_fee": l["bag_fee"],
        "bag_note": l["bag_note"],
        "bags": l["bags"],
        "airlines": l["airlines"],
        "airline_code": (l.get("segments") or [["", "", "", ""]])[0][3],
        "route": l["route"],
        "depart": l["depart"],
        "arrive": l.get("arrive"),
        "stops": l["stops"],
        "duration_min": l["duration_min"],
        "return_flight": l.get("return_flight"),
        "booking": l.get("booking") or [],
        "booking_url": l.get("booking_url"),
        "google_url": l["url"],
        "links": links,
    }


def write_trip_json(path, cfg, advice, best, dvs, timing, db, generated_at, main_key):
    winner_name, winner = min(best.items(), key=lambda kv: kv[1]["total"])
    data = {
        "generated_at": generated_at.isoformat(timespec="minutes"),
        "trip_name": cfg["trip_name"],
        "plan": {
            "outbound_dates": cfg["outbound_dates"],
            "return_dates": cfg["return_dates"],
            "seoul_to_tokyo_dates": cfg["seoul_to_tokyo_dates"],
            "tokyo_to_seoul_dates": cfg["tokyo_to_seoul_dates"],
            "bags": cfg["bags"],
        },
        "advice": {
            "action": advice.action,
            "reason": advice.reason,
            "price": advice.price,
            "min_seen": advice.min_seen,
            "typical_low": advice.typical_low,
            "typical_high": advice.typical_high,
            "level": advice.level,
            "trend_per_week": advice.trend_per_week,
            "forecast_14d": advice.forecast_14d,
            "days_left": advice.days_left,
            "window": list(advice.window),
        },
        "best": {"strategy": winner_name, "label": STRATEGIES[winner_name], "total": winner["total"],
                 "legs": [_leg(l) for l in winner["legs"]]},
        "strategies": [{"name": n, "label": STRATEGIES[n], "total": c["total"]}
                       for n, c in sorted(best.items(), key=lambda kv: kv[1]["total"])],
        "direct_vs_stop": dvs,
        "series": {n: db.combo_series(n) for n in STRATEGIES},
        "google_history": db.google_history(main_key),
        "timing": timing,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
