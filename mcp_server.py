"""Serveur MCP "google-flights" : donne à Claude un accès direct, en temps réel, à Google Flights.

Lancé automatiquement par Claude Code (.mcp.json) ou Claude Desktop (claude_desktop_config.json).
Transport stdio : ne jamais écrire sur stdout ici.
"""

import json
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from tracker.bags import bag_cost
from tracker.gflights import GoogleFlights, SearchResult

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "prices.db"

server = MCPServer("google-flights")


def _fmt_result(title: str, res: SearchResult, limit: int, bags: list[int] | None = None) -> str:
    lines = [f"## {title}", f"Lien Google Flights : {res.url}"]
    ins = res.insights
    if ins and ins.typical_low is not None:
        lines.append(
            f"Price insights Google : prix actuel {ins.current} €, fourchette habituelle "
            f"{ins.typical_low}–{ins.typical_high} € → niveau **{ins.level}**"
        )
        if ins.history:
            first, last = ins.history[0], ins.history[-1]
            lines.append(f"Historique Google : {first[1]} € le {first[0]} → {last[1]} € le {last[0]} ({len(ins.history)} points)")
    bags = bags or []
    priced = sorted(((o.price + bag_cost(o.airlines, o.duration_min, bags)[0], o) for o in res.offers), key=lambda t: t[0])
    if not priced:
        lines.append("Aucun vol trouvé.")
    if bags:
        lines.append(f"Classement valises comprises ({' / '.join(map(str, bags))} valise(s) 23 kg par sens, frais estimés par compagnie) :")
    for total, o in priced[:limit]:
        stops = "direct" if o.stops == 0 else f"{o.stops} escale(s)"
        with_bags = f" (billet {o.price} € + valises {total - o.price} €)" if bags else ""
        lines.append(
            f"- **{total} €**{with_bags} · {', '.join(o.airlines)} · {o.route} · {stops} · "
            f"départ {o.depart} → arrivée {o.arrive} · {o.duration_min // 60}h{o.duration_min % 60:02d}"
        )
    return "\n".join(lines)


def _legs(origin, destination, departure_date, return_date):
    legs = [(departure_date, origin.upper(), destination.upper())]
    if return_date:
        legs.append((return_date, destination.upper(), origin.upper()))
    return legs


@server.tool()
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    max_stops: int | None = 1,
    adults: int = 1,
    currency: str = "EUR",
    limit: int = 8,
    bags_outbound: int = 1,
    bags_return: int = 2,
) -> str:
    """Recherche en direct sur Google Flights (prix actuels, classés du moins cher au plus cher).

    origin / destination : code IATA d'aéroport ou de ville, plusieurs possibles avec "+" (ex. "CDG+ORY", SEL, TYO, OSA).
    L'utilisateur part uniquement de CDG ou Orly : utiliser "CDG+ORY" pour Paris (jamais PAR, qui inclut Beauvais).
    departure_date / return_date : AAAA-MM-JJ. Sans return_date = aller simple.
    max_stops : 0 = direct uniquement, 1 = une escale max (défaut), null = illimité.
    bags_outbound / bags_return : valises 23 kg en soute par sens (défaut 1 à l'aller, 2 au retour) ;
    le classement se fait valises comprises (frais estimés par compagnie, Google ne les fournit pas).
    Renvoie aussi les "Price insights" de Google (fourchette de prix habituelle + historique récent).
    """
    gf = GoogleFlights(currency=currency, adults=adults)
    res = gf.search(_legs(origin, destination, departure_date, return_date), max_stops)
    kind = "A/R" if return_date else "Aller simple"
    dates = f"{departure_date} → {return_date}" if return_date else departure_date
    bags = [bags_outbound, bags_return] if return_date else [bags_outbound]
    return _fmt_result(f"{kind} {origin.upper()}→{destination.upper()} {dates}", res, limit, bags)


@server.tool()
def compare_stops(origin: str, destination: str, departure_date: str, return_date: str | None = None) -> str:
    """Compare le vol le moins cher en direct, avec 1 escale max et sans limite d'escales."""
    gf = GoogleFlights()
    legs = _legs(origin, destination, departure_date, return_date)
    out = []
    for label, stops in (("Direct", 0), ("1 escale max", 1), ("Escales illimitées", None)):
        best = gf.search(legs, stops).best
        out.append(f"- {label} : " + (f"**{best.price} €** · {', '.join(best.airlines)} · {best.route}" if best else "aucun vol"))
        time.sleep(2)
    return "\n".join(out)


@server.tool()
def flexible_dates(
    origin: str,
    destination: str,
    departure_date: str,
    trip_days: int | None = None,
    flex_days: int = 2,
    max_stops: int | None = 1,
) -> str:
    """Teste les dates de départ autour de departure_date (± flex_days, max 3) pour trouver le jour le moins cher.

    trip_days : durée du séjour pour un A/R (ex. 28) ; omis = aller simple.
    """
    flex_days = min(flex_days, 3)
    gf = GoogleFlights()
    base = date.fromisoformat(departure_date)
    rows = []
    for delta in range(-flex_days, flex_days + 1):
        d = base + timedelta(days=delta)
        ret = (d + timedelta(days=trip_days)).isoformat() if trip_days else None
        best = gf.search(_legs(origin, destination, d.isoformat(), ret), max_stops).best
        label = f"{d.isoformat()}" + (f" → {ret}" if ret else "")
        rows.append((best.price if best else None, label, best))
        time.sleep(2)
    rows.sort(key=lambda r: (r[0] is None, r[0]))
    return "\n".join(
        f"- {label} : " + (f"**{p} €** · {', '.join(b.airlines)} · {b.route}" if b else "aucun vol")
        for p, label, b in rows
    )


@server.tool()
def trip_tracker_status() -> str:
    """État du tracker Séoul/Japon été 2027 : dernier relevé, meilleure combinaison par stratégie,
    recommandation (ACHETER / SURVEILLER / ATTENDRE) et évolution du meilleur prix."""
    if not DB_PATH.exists():
        return "Aucun relevé pour l'instant (lancer `python run.py`)."
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    last = conn.execute("SELECT id, ts, errors FROM runs WHERE id IN (SELECT run_id FROM combos) ORDER BY id DESC LIMIT 1").fetchone()
    if last is None:
        return "Aucun relevé complet pour l'instant."
    lines = [f"Dernier relevé : {last['ts']} ({last['errors']} erreurs)"]
    action = conn.execute("SELECT v FROM state WHERE k='last_action'").fetchone()
    if action:
        lines.append(f"Recommandation : **{json.loads(action['v'])}**")
    for r in conn.execute("SELECT strategy, total, details FROM combos WHERE run_id=? ORDER BY total", (last["id"],)):
        lines.append(f"\n### {r['strategy']} : {r['total']} €")
        for l in json.loads(r["details"])["legs"]:
            lines.append(f"- {l['search']} : {l['price']} € · {l['airlines']} · {l['route']} · {l['url']}")
    series = conn.execute("SELECT ts, MIN(total) t FROM combos GROUP BY run_id ORDER BY ts").fetchall()
    lines.append("\nÉvolution du meilleur total : " + ", ".join(f"{s['ts'][:16]} {s['t']} €" for s in series[-15:]))
    return "\n".join(lines)


@server.tool()
def price_history(search_key: str = "RT CDG+ORY-SEL 2027-07-22/2027-08-19") -> str:
    """Historique quotidien des prix fourni par Google pour une recherche suivie par le tracker
    (clé au format 'RT PAR-SEL AAAA-MM-JJ/AAAA-MM-JJ' ou 'OW SEL-TYO AAAA-MM-JJ')."""
    if not DB_PATH.exists():
        return "Base vide."
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT day, price FROM google_history WHERE key=? ORDER BY day", (search_key,)).fetchall()
    if not rows:
        keys = [k for (k,) in conn.execute("SELECT DISTINCT key FROM google_history ORDER BY key")]
        return "Clé inconnue. Clés disponibles :\n" + "\n".join(keys)
    return "\n".join(f"{d} : {p} €" for d, p in rows)


@server.tool()
def booking_options(origin: str, destination: str, departure_date: str, max_stops: int | None = 1, flights: int = 2) -> str:
    """Où réserver : prix du même billet (aller simple) sur chaque site proposé par Google Flights
    (site de la compagnie, Trip.com, Gotogate, Opodo…), pour les `flights` vols les moins chers (max 4).
    Utiliser "CDG+ORY" pour Paris."""
    from tracker.booking import BookingBrowser

    res = GoogleFlights().search(_legs(origin, destination, departure_date, None), max_stops)
    offers = sorted(res.offers, key=lambda o: o.price)[: min(flights, 4)]
    out = []
    with BookingBrowser() as b:
        for o in offers:
            try:
                opts, url = b.options(o.segments)
            except Exception as e:
                out.append(f"### {', '.join(o.airlines)} {o.route} ({o.price} €)\nOptions indisponibles : {e}")
                continue
            lines = [f"### {', '.join(o.airlines)} · {o.route} · départ {o.depart} (liste : {o.price} €)", url]
            lines += [f"- {x['site']}{' (compagnie)' if x['airline'] else ''} : **{x['price']} €**" for x in opts]
            out.append("\n".join(lines))
    return "\n\n".join(out) or "Aucun vol trouvé."


if __name__ == "__main__":
    server.run()
