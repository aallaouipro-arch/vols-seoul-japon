"""Quand les prix bougent-ils ? Statistiques par jour de la semaine et par heure.

- Jour de la semaine : variations jour après jour de l'historique Google (~60 j
  par recherche, toutes recherches confondues) + nos propres relevés.
- Heure : uniquement nos relevés (4 par jour), donc fiable après quelques semaines.
"""

from collections import defaultdict
from datetime import date, datetime

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _changes(points):
    """[(moment, prix)] triés → [(moment, variation en %)] entre points consécutifs."""
    out = []
    for (_, p0), (t1, p1) in zip(points, points[1:]):
        if p0:
            out.append((t1, (p1 - p0) / p0 * 100))
    return out


def _summarize(buckets, labels):
    rows = []
    for k in labels:
        vals = buckets.get(k, [])
        if not vals:
            continue
        drops = [v for v in vals if v < -0.5]
        rises = [v for v in vals if v > 0.5]
        rows.append({
            "label": k,
            "n": len(vals),
            "drop_rate": round(len(drops) / len(vals) * 100),
            "rise_rate": round(len(rises) / len(vals) * 100),
            "avg_change_pct": round(sum(vals) / len(vals), 2),
        })
    return rows


def price_timing(db) -> dict:
    by_weekday, by_hour = defaultdict(list), defaultdict(list)

    # Historique Google : 1 point par jour et par recherche
    keys = [r[0] for r in db.conn.execute("SELECT DISTINCT key FROM google_history")]
    for k in keys:
        pts = [(date.fromisoformat(d), p) for d, p in db.google_history(k)]
        for d, pct in _changes(pts):
            by_weekday[JOURS[d.weekday()]].append(pct)

    # Nos relevés : meilleur tarif de chaque recherche à chaque relevé
    rows = db.conn.execute(
        "SELECT key, ts, best_price FROM searches WHERE best_price IS NOT NULL ORDER BY key, ts"
    ).fetchall()
    series = defaultdict(list)
    for k, ts, p in rows:
        series[k].append((datetime.fromisoformat(ts), p))
    for pts in series.values():
        for t, pct in _changes(pts):
            by_hour[f"{t.hour:02d}h"].append(pct)

    weekday = _summarize(by_weekday, JOURS)
    hours = _summarize(by_hour, sorted(by_hour))
    best_day = max(weekday, key=lambda r: r["drop_rate"], default=None)
    best_hour = max(hours, key=lambda r: r["drop_rate"], default=None) if sum(r["n"] for r in hours) >= 200 else None
    return {"weekday": weekday, "hours": hours, "best_day": best_day, "best_hour": best_hour}
