"""Tendance, prédiction et recommandation d'achat.

Heuristique (pas de boule de cristal) basée sur :
- la fourchette de prix "habituelle" que Google calcule pour chaque trajet ;
- la tendance récente (régression linéaire sur l'historique) ;
- le plus bas prix déjà observé ;
- le nombre de jours avant le départ (fenêtre conseillée configurable).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass
class Advice:
    action: str  # ACHETER / SURVEILLER / ATTENDRE
    reason: str
    price: int
    typical_low: int | None
    typical_high: int | None
    level: str
    min_seen: int
    trend_per_week: float | None
    forecast_14d: int | None
    days_left: int
    window: tuple[str, str]  # fenêtre d'achat conseillée (dates ISO)


def daily_min(series: list[tuple[str, int]]) -> list[tuple[date, int]]:
    by_day: dict[date, int] = {}
    for ts, price in series:
        d = date.fromisoformat(ts[:10])
        by_day[d] = min(price, by_day.get(d, price))
    return sorted(by_day.items())


def slope_per_day(points: list[tuple[date, int]], last_days=21) -> float | None:
    """Pente (€/jour) des moindres carrés sur les `last_days` derniers jours."""
    if not points:
        return None
    cutoff = points[-1][0] - timedelta(days=last_days)
    pts = [(d, p) for d, p in points if d >= cutoff]
    if len(pts) < 4:
        return None
    xs = [(d - pts[0][0]).days for d, _ in pts]
    ys = [p for _, p in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var


def typical_range(legs, results) -> tuple[int | None, int | None]:
    """Somme des fourchettes habituelles Google de chaque vol de la combinaison,
    + les frais de valises (Google raisonne sans bagages)."""
    lo = hi = 0
    for leg in legs:
        ins = results[leg["search"]].insights
        if not ins or ins.typical_low is None or ins.typical_high is None:
            return None, None
        lo += ins.typical_low + leg.get("bag_fee", 0)
        hi += ins.typical_high + leg.get("bag_fee", 0)
    return lo, hi


def advise(cfg, best: dict, results, own_series, proxy_history, today=None) -> Advice:
    """
    best          : meilleure combinaison actuelle {total, legs}
    own_series    : [(ts, total)] meilleurs totaux relevés par le tracker
    proxy_history : [(jour, prix)] historique Google du vol long-courrier principal,
                    utilisé pour la tendance tant qu'on n'a pas assez de relevés à nous
    """
    today = today or date.today()
    ba = cfg["booking_advice"]
    first_departure = date.fromisoformat(min(cfg["outbound_dates"]))
    days_left = (first_departure - today).days
    far, near = max(ba["sweet_spot_days_before"]), min(ba["sweet_spot_days_before"])
    window = (
        (first_departure - timedelta(days=far)).isoformat(),
        (first_departure - timedelta(days=near)).isoformat(),
    )

    price = best["total"]
    lo, hi = typical_range(best["legs"], results)
    if lo is None:
        level = "inconnu"
    elif price < lo:
        level = "bas"
    elif price > hi:
        level = "élevé"
    else:
        level = "habituel"

    own = daily_min(own_series)
    min_seen = min([p for _, p in own] + [price])

    # Tendance : nos relevés si on a ≥ 7 jours de données, sinon l'historique Google du vol principal
    if len(own) >= 7:
        slope = slope_per_day(own)
    else:
        slope = slope_per_day([(date.fromisoformat(d), p) for d, p in proxy_history])
    trend_week = round(slope * 7, 1) if slope is not None else None
    forecast = round(price + slope * 14) if slope is not None else None

    rising = slope is not None and slope * 7 > price * 0.01  # > +1 %/semaine
    at_low = price <= min_seen * 1.02

    if level == "bas":
        action, reason = "ACHETER", f"prix sous la fourchette habituelle Google ({lo}–{hi} €)"
    elif days_left <= ba["deadline_days_before"]:
        action = "ACHETER"
        reason = f"plus que {days_left} j avant le départ : en haute saison les prix montent quasi toujours à l'approche du départ"
    elif days_left > far:
        if level == "habituel" and rising:
            action = "SURVEILLER"
            reason = (f"prix correct mais en hausse ({slope * 7:+.0f} €/sem) ; encore loin de la fenêtre conseillée, "
                      "je préviens si ça s'emballe ou si une promo passe sous la fourchette habituelle")
        elif level == "habituel" and at_low:
            action, reason = "SURVEILLER", "prix correct et au plus bas observé, mais on est encore loin de la fenêtre conseillée"
        else:
            action, reason = "ATTENDRE", f"trop tôt : la fenêtre d'achat conseillée commence le {window[0]}"
    elif at_low and level == "habituel":
        action, reason = "ACHETER", "dans la fenêtre conseillée, prix habituel et au plus bas jamais relevé"
    elif rising and level != "élevé":
        action, reason = "ACHETER", "dans la fenêtre conseillée et la tendance est à la hausse"
    else:
        action = "SURVEILLER"
        reason = "dans la fenêtre conseillée : j'attends une baisse ou un prix au plus bas"

    return Advice(
        action=action,
        reason=reason,
        price=price,
        typical_low=lo,
        typical_high=hi,
        level=level,
        min_seen=min_seen,
        trend_per_week=trend_week,
        forecast_14d=forecast,
        days_left=days_left,
        window=window,
    )


def now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")
