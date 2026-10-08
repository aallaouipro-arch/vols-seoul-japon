"""Définit les recherches à lancer et combine les résultats en itinéraires complets.

Itinéraire voulu : Paris (CDG/ORY) → Séoul (1 semaine) → Japon (~3 semaines) → Paris (CDG/ORY).
Google Flights ne renvoie pas les résultats "multi-destinations" côté serveur,
donc on reconstitue le voyage à partir d'allers simples et d'allers-retours.

Leviers de prix pris en compte :
- 1 escale max (≈ 250 € de moins que le direct Paris↔Séoul) ;
- dates flexibles, dont des départs mardi/mercredi (en moyenne moins chers) ;
- vols simples combinés (open-jaw) vs aller-retour ;
- valises : chaque vol est comparé valises comprises (ex. 1×23 kg à l'aller,
  2×23 kg au retour), ce qui avantage les compagnies qui les incluent (JAL…).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product

from .bags import bag_cost

STRATEGIES = {
    "open_jaw": "3 allers simples : Paris→Séoul, Séoul→Japon, Japon→Paris",
    "rt_seoul": "A/R Paris↔Séoul + Séoul→Japon + Japon→Séoul",
    "rt_tokyo": "A/R Paris↔Tokyo + crochet Tokyo→Séoul→Japon",
    "single_ticket": "Billet unique Paris→Séoul / Japon→Paris + Séoul→Japon",
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


def _next_day(d: str) -> str:
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def _plan(cfg):
    """Toutes les briques de voyage possibles : {nom: [(legs, bags)]} indexées par dates."""
    P, S, J = cfg["origin"], cfg["seoul"], cfg["japan_cities"]
    s2j, j2s = cfg["seoul_to_japan_date"], cfg["japan_to_seoul_date"]
    b_out, b_ret = cfg["bags"]["outbound"], cfg["bags"]["return"]
    return {
        "out_ow": lambda o: ([(o, P, S)], [b_out]),
        "seoul_japan": lambda j: ([(s2j, S, j)], [b_out]),
        "japan_home": lambda j, r: ([(r, j, P)], [b_ret]),
        "rt_seoul": lambda o, r: ([(o, P, S), (r, S, P)], [b_out, b_ret]),
        "japan_seoul": lambda j: ([(j2s, j, S)], [b_ret]),
        "rt_tokyo": lambda o, r: ([(o, P, "TYO"), (r, "TYO", P)], [b_out, b_ret]),
        "tokyo_seoul": lambda o: ([(_next_day(o), "TYO", S)], [b_out]),
    }


def build_searches(cfg) -> list[Search]:
    """Recherches lancées à chaque relevé."""
    J, outs, rets = cfg["japan_cities"], cfg["outbound_dates"], cfg["return_dates"]
    p = _plan(cfg)
    bricks = (
        [p["out_ow"](o) for o in outs]
        + [p["seoul_japan"](j) for j in J]
        + [p["japan_home"](j, r) for j, r in product(J, rets)]
        + [p["rt_seoul"](o, r) for o, r in product(outs, rets)]
        + [p["japan_seoul"](j) for j in J]
        + [p["rt_tokyo"](o, r) for o, r in product(outs, rets)]
        + [p["tokyo_seoul"](o) for o in outs]
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
        leg = _leg(results, *p["rt_seoul"](o, r))
        if leg:
            pairs.append((leg["total"], o, r))
    return min(pairs)[1:] if pairs else None


def build_followup_searches(cfg, results) -> list[Search]:
    """Après la 1re phase : le direct Paris↔Séoul aux meilleures dates, pour comparaison."""
    pair = best_rt_pair(cfg, results)
    if pair is None:
        return []
    legs, bags = _plan(cfg)["rt_seoul"](*pair)
    return [Search(legs, bags, max_stops=0)]


def _leg(results, legs, bags, direct=False):
    """Vol le moins cher valises comprises pour une recherche, ou None."""
    k = key(legs, direct)
    res = results.get(k)
    if res is None or not res.offers:
        return None
    priced = []
    for o in res.offers:
        extra, note = bag_cost(o.airlines, o.duration_min, bags)
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
    J, outs, rets = cfg["japan_cities"], cfg["outbound_dates"], cfg["return_dates"]
    p = _plan(cfg)
    L = lambda brick: _leg(results, *brick)  # noqa: E731

    candidates = {name: [] for name in STRATEGIES}
    for o, r in product(outs, rets):
        for j_in, j_out in product(J, J):
            candidates["open_jaw"].append(
                [L(p["out_ow"](o)), L(p["seoul_japan"](j_in)), L(p["japan_home"](j_out, r))]
            )
            candidates["rt_seoul"].append(
                [L(p["rt_seoul"](o, r)), L(p["seoul_japan"](j_in)), L(p["japan_seoul"](j_out))]
            )
        for j_in in J:
            candidates["rt_tokyo"].append(
                [L(p["rt_tokyo"](o, r)), L(p["tokyo_seoul"](o)), L(p["seoul_japan"](j_in))]
            )

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
    legs, bags = _plan(cfg)["rt_seoul"](*pair)
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
