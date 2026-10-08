"""Page "Options de réservation" de Google Flights : prix du même vol site par site
(compagnie, Trip.com, Gotogate, Opodo…).

Cette page est remplie en JavaScript après le chargement : on passe par un vrai
navigateur sans écran (Playwright + Chromium). Seuls les allers simples sont
gérés : pour un aller-retour, Google demande d'abord de choisir le vol retour.
"""

import logging
import re
from base64 import urlsafe_b64encode

from .gflights import CONSENT_COOKIE, _field, _varint

log = logging.getLogger("tracker")

BOOKING_URL = "https://www.google.com/travel/flights/booking"
PRICE_RE = re.compile(r"^(\d[\d\s  ]*)\s?€$")


def _s(tag: int, text: str) -> bytes:
    return _field(tag, text.encode())


def booking_url(segments, currency="EUR", language="fr") -> str:
    """URL de la page de réservation d'un vol (aller simple) à partir de ses segments
    [(départ, date, arrivée, compagnie, n° de vol)]."""
    date = segments[0][1]
    leg = _s(0x12, date)
    for frm, d, to, airline, num in segments:
        leg += _field(0x22, _s(0x0A, frm) + _s(0x12, d) + _s(0x1A, to) + _s(0x2A, airline) + _s(0x32, num))
    leg += _field(0x6A, b"\x08\x01" + _s(0x12, segments[0][0]))
    leg += _field(0x72, b"\x08\x01" + _s(0x12, segments[-1][2]))
    # 1=28, 2=2, vol, 8=adulte, 9=éco, 14=1, 19=aller simple (même en-tête que Google)
    raw = b"\x08\x1c\x10\x02" + _field(0x1A, leg) + b"\x40\x01\x48\x01\x70\x01" + b"\x98\x01" + _varint(2)
    tfs = urlsafe_b64encode(raw).decode().rstrip("=")
    return f"{BOOKING_URL}?tfs={tfs}&hl={language}&gl=FR&curr={currency}"


def parse_options(text: str) -> list[dict]:
    """Texte de la page → [{site, price, airline}] trié par prix."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        if not line.startswith("Réserver avec "):
            continue
        name = line.removeprefix("Réserver avec ")
        airline = name.endswith("Compagnie aérienne")
        name = name.removesuffix("Compagnie aérienne").strip()
        for nxt in lines[i + 1:i + 4]:
            if m := PRICE_RE.match(nxt):
                out.append({"site": name, "price": int(re.sub(r"\D", "", m.group(1))), "airline": airline})
                break
    return sorted(out, key=lambda o: o["price"])


class BookingBrowser:
    """Un seul navigateur pour toutes les pages d'un relevé."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        ctx = self._browser.new_context(locale="fr-FR", viewport={"width": 1280, "height": 2000})
        ctx.add_cookies([
            {"name": k, "value": v, "domain": ".google.com", "path": "/"}
            for k, v in (c.split("=", 1) for c in CONSENT_COOKIE.split("; "))
        ])
        self._page = ctx.new_page()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def options(self, segments, currency="EUR") -> tuple[list[dict], str]:
        url = booking_url(segments, currency)
        page = self._page
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_function(
            "() => !document.body.innerText.includes('Récupération des prix')"
            " && document.body.innerText.includes('Réserver avec')",
            timeout=45000,
        )
        return parse_options(page.inner_text("body")), url


def attach_booking_options(legs: list[dict], currency="EUR") -> None:
    """Ajoute leg["booking"] (prix par site) aux allers simples de la combinaison."""
    todo = [l for l in legs if l["search"].startswith("OW ") and l.get("segments")]
    if not todo:
        return
    try:
        with BookingBrowser() as b:
            for leg in todo:
                try:
                    opts, url = b.options(leg["segments"], currency)
                    leg["booking"], leg["booking_url"] = opts, url
                    log.info("Options de réservation %s : %s", leg["search"],
                             ", ".join(f"{o['site']} {o['price']} €" for o in opts[:4]) or "aucune")
                except Exception as e:
                    log.warning("Options de réservation %s indisponibles : %s", leg["search"], e)
    except Exception as e:  # Playwright absent ou navigateur qui ne démarre pas : on continue sans
        log.warning("Navigateur indisponible, pas d'options de réservation : %s", e)


def booking_summary(leg: dict) -> str:
    """Ex. "Gotogate 546 € (agence) · Lufthansa 551 € (compagnie, +5 €)"."""
    opts = leg.get("booking") or []
    if not opts:
        return ""
    cheapest = opts[0]
    airline = next((o for o in opts if o["airline"]), None)
    parts = [f"{cheapest['site']} {cheapest['price']} € ({'compagnie' if cheapest['airline'] else 'agence'})"]
    if airline and airline is not cheapest:
        parts.append(f"{airline['site']} {airline['price']} € (compagnie, +{airline['price'] - cheapest['price']} €)")
    elif len(opts) > 1:
        others = opts[1:]
        same = sum(o["price"] == cheapest["price"] for o in others)
        dearer = [o for o in others if o["price"] > cheapest["price"]]
        if same:
            parts.append(f"{same} autre{'s' if same > 1 else ''} site{'s' if same > 1 else ''} au même prix")
        if dearer:
            parts.append(f"{len(dearer)} agence{'s' if len(dearer) > 1 else ''} plus chère{'s' if len(dearer) > 1 else ''} (dès {dearer[0]['price']} €)")
    return " · ".join(parts)


# --- Billet unique multi-destinations (rendu en JavaScript, donc via le navigateur) ---

def multicity_url(legs, adults=1, max_stops=1, currency="EUR") -> str:
    from .gflights import _encode_tfs

    tfs = _encode_tfs(legs, trip="multi-city", adults=adults, max_stops=max_stops)
    return f"https://www.google.com/travel/flights/search?tfs={tfs}&hl=fr&gl=FR&curr={currency}"


def _parse_result_item(text: str) -> dict | None:
    """Texte d'une ligne de résultat Google Flights → {price, airlines, route, depart_time, duration, stops}."""
    lines = [l.strip() for l in text.replace("\xa0", " ").splitlines() if l.strip()]
    price = next((int(re.sub(r"\D", "", l)) for l in lines if PRICE_RE.match(l)), None)
    if price is None or len(lines) < 7:
        return None
    return {
        "price": price,
        "airlines": lines[3],
        "duration": lines[4],
        "route": lines[5],
        "stops": 0 if lines[6].lower().startswith("sans escale") else int(re.sub(r"\D", "", lines[6]) or 1),
        "depart_time": lines[0],
    }


def _browser_search(b, url) -> list[dict]:
    page = b._page
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_selector("li.pIav2d", timeout=45000)
    page.wait_for_timeout(1500)  # la liste se complète après le premier rendu
    items = [_parse_result_item(t) for t in page.locator("li.pIav2d").all_inner_texts()]
    return sorted((i for i in items if i), key=lambda i: i["price"])


def single_ticket_combo(cfg, results) -> dict | None:
    """Meilleur montage "billet unique" : Paris→Séoul + Japon→Paris sur UN billet
    (multi-destinations), + Séoul→Japon séparé. Aux dates du meilleur A/R."""
    from .bags import bag_cost
    from .plan import _leg, _plan, best_rt_pair

    pair = best_rt_pair(cfg, results)
    if pair is None:
        return None
    o, r = pair
    P, S = cfg["origin"], cfg["seoul"]
    bags = [cfg["bags"]["outbound"], cfg["bags"]["return"]]
    best = None
    try:
        with BookingBrowser() as b:
            for j in cfg["japan_cities"]:
                legs = [(o, P, S), (r, j, P)]
                url = multicity_url(legs, max_stops=cfg.get("max_stops", 1), currency=cfg["currency"])
                try:
                    items = _browser_search(b, url)
                except Exception as e:
                    log.warning("Billet unique %s→%s / %s→%s indisponible : %s", P, S, j, P, e)
                    continue
                if not items:
                    continue
                priced = []
                for it in items:
                    extra, note = bag_cost([it["airlines"]], 12 * 60, bags)
                    priced.append((it["price"] + extra, extra, note, it))
                total, extra, note, it = min(priced, key=lambda t: t[0])
                ticket = {
                    "search": f"MC {P}-{S} {o} + {j}-{P} {r}",
                    "price": total, "fare": it["price"], "bag_fee": extra, "bag_note": note, "bags": bags,
                    "airlines": it["airlines"], "route": f"{it['route']} … {j}→Paris",
                    "depart": f"{o} {it['depart_time']}", "arrive": "", "stops": it["stops"],
                    "duration_min": 0, "url": url, "total": total, "segments": [],
                }
                hop = _leg(results, *_plan(cfg)["seoul_japan"](j))
                if hop is None:
                    continue
                combo = {"total": ticket["price"] + hop["price"], "legs": [ticket, hop]}
                log.info("Billet unique via %s : %d € (billet %d € + valises %d €) + Séoul→Japon %d €",
                         j, combo["total"], it["price"], extra, hop["price"])
                if best is None or combo["total"] < best["total"]:
                    best = combo
    except Exception as e:
        log.warning("Navigateur indisponible, pas de billet unique : %s", e)
    return best
