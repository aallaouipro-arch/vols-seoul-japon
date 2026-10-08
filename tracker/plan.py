"""Définit les recherches à lancer et combine les résultats en itinéraires complets.

Plan de l'utilisateur (chacun achète son billet, 1 personne) :
- billet 1 : aller-retour Paris (CDG/ORY) ↔ Séoul, le retour en France part de Séoul ;
- billet 2 : aller-retour Séoul ↔ Tokyo, retour à Séoul avant le vol pour Paris.

Leviers de prix pris en compte :
- 1 escale max (≈ 250 € de moins que le direct Paris↔Séoul) ;
- dates flexibles, dont des départs mardi/mercredi (en moyenne moins chers) ;
- Séoul↔Tokyo en aller-retour ou en 2 allers simples (souvent identique chez les low-cost) ;
- valises : chaque vol est comparé valises comprises (1×23 kg à l'aller, 2×23 kg au retour).
"""

from dataclasses import dataclass, field
from itertools import product

from .bags import bag_cost

STRATEGIES = {
    "two_rt": "A/R Paris↔Séoul + A/R Séoul↔Tokyo",
    "rt_two_ow": "A/R Paris↔Séoul + Séoul↔Tokyo en 2 allers simples",
}


@dataclass
class Search:
    legs: list[tuple[str, str, str]]
    bags: list[int] = field(default_factory=list)  # valises par sens : [aller] ou [aller, retour]
    max_stops: int | None = -1  # -1 = valeur de config

    @property
    def key(self) -> str:
        return key(self.legs, direct=self.max_stops == 0)


def key(legs, direct=False) -> str:
    suffix = " direct" if direct else ""
    if len(legs) == 1:
        d, a, b = legs[0]
        return f"OW {a}-{b} {d}{suffix}"
    (d1, a, b), (d2, _, _) = legs
    return f"RT {a}-{b} {d1}/{d2}{suffix}"


def _plan(cfg):
    """Briques de voyage : nom → fonction(dates) → (legs, valises par sens)."""
    P, S, T = cfg["origin"], cfg["seoul"], cfg["tokyo"]
    b_out, b_ret = cfg["bags"]["outbound"], cfg["bags"]["return"]
    return {
        "rt_paris": lambda o, r: ([(o, P, S), (r, S, P)], [b_out, b_ret]),
        "rt_tokyo": lambda go, back: ([(go, S, T), (back, T, S)], [b_out, b_ret]),
        "ow_to_tokyo": lambda go: ([(go, S, T)], [b_out]),
        "ow_from_tokyo": lambda back: ([(back, T, S)], [b_ret]),
    }


def _tokyo_pairs(cfg, paris_return=None):
    """(aller, retour) Séoul↔Tokyo, retour à Séoul avant le vol pour Paris."""
    return [
        (go, back)
        for go, back in product(cfg["seoul_to_tokyo_dates"], cfg["tokyo_to_seoul_dates"])
        if paris_return is None or back < paris_return
    ]


def build_searches(cfg) -> list[Search]:
    """Recherches lancées à chaque relevé."""
    p = _plan(cfg)
    bricks = (
        [p["rt_paris"](o, r) for o, r in product(cfg["outbound_dates"], cfg["return_dates"])]
        + [p["rt_tokyo"](go, back) for go, back in _tokyo_pairs(cfg)]
        + [p["ow_to_tokyo"](go) for go in cfg["seoul_to_tokyo_dates"]]
        + [p["ow_from_tokyo"](back) for back in cfg["tokyo_to_seoul_dates"]]
    )
    seen = {}
    for legs, bags in bricks:
        s = Search(legs, bags)
        seen.setdefault(s.key, s)
    return list(seen.values())


def best_rt_pair(cfg, results) -> tuple[str, str] | None:
    """Dates (aller, retour) de l'A/R Paris↔Séoul le moins cher (valises comprises)."""
    p = _plan(cfg)
    pairs = []
    for o, r in product(cfg["outbound_dates"], cfg["return_dates"]):
        leg = _leg(results, *p["rt_paris"](o, r))
        if leg:
            pairs.append((leg["total"], o, r))
    return min(pairs)[1:] if pairs else None


def build_followup_searches(cfg, results) -> list[Search]:
    """Après la 1re phase : le direct Paris↔Séoul aux meilleures dates, pour comparaison."""
    pair = best_rt_pair(cfg, results)
    if pair is None:
        return []
    legs, bags = _plan(cfg)["rt_paris"](*pair)
    return [Search(legs, bags, max_stops=0)]


def _leg(results, legs, bags, direct=False):
    """Vol le moins cher valises comprises pour une recherche, ou None."""
    k = key(legs, direct)
    res = results.get(k)
    if res is None or not res.offers:
        return None
    priced = []
    for o in res.offers:
        extra, note = bag_cost(o.airlines, o.duration_min, bags, o.airline_code)
        priced.append((o.price + extra, extra, note, o))
    total, extra, note, o = min(priced, key=lambda t: t[0])
    return {
        "search": k,
        "price": total,  # billet + valises
        "fare": o.price,
        "bag_fee": extra,
        "bag_note": note,
        "bags": bags,
        "airlines": ", ".join(o.airlines),
        "route": o.route,
        "depart": o.depart,
        "arrive": o.arrive,
        "stops": o.stops,
        "duration_min": o.duration_min,
        "url": res.url,
        "total": total,
        "segments": o.segments,
        "query": legs,
    }


def best_combos(cfg, results) -> dict[str, dict]:
    """Pour chaque stratégie, la combinaison la moins chère : {strategy: {total, legs}}."""
    p = _plan(cfg)
    L = lambda brick: _leg(results, *brick)  # noqa: E731

    candidates = {name: [] for name in STRATEGIES}
    for o, r in product(cfg["outbound_dates"], cfg["return_dates"]):
        for go, back in _tokyo_pairs(cfg, paris_return=r):
            paris = L(p["rt_paris"](o, r))
            candidates["two_rt"].append([paris, L(p["rt_tokyo"](go, back))])
            candidates["rt_two_ow"].append([paris, L(p["ow_to_tokyo"](go)), L(p["ow_from_tokyo"](back))])

    best = {}
    for name, combos in candidates.items():
        complete = [c for c in combos if all(c)]
        if complete:
            legs = min(complete, key=lambda c: sum(l["price"] for l in c))
            best[name] = {"total": sum(l["price"] for l in legs), "legs": legs}
    return best


def direct_vs_stop(cfg, results) -> dict | None:
    """Compare direct et 1 escale (valises comprises) sur l'A/R Paris↔Séoul aux meilleures dates."""
    pair = best_rt_pair(cfg, results)
    if pair is None:
        return None
    legs, bags = _plan(cfg)["rt_paris"](*pair)
    stop, direct = _leg(results, legs, bags), _leg(results, legs, bags, direct=True)
    if not (stop and direct):
        return None
    return {
        "dates": f"{pair[0]} → {pair[1]}",
        "direct": direct["price"],
        "direct_airlines": direct["airlines"],
        "one_stop": stop["price"],
        "one_stop_airlines": stop["airlines"],
        "one_stop_route": stop["route"],
        "saving": direct["price"] - stop["price"],
    }
