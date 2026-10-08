"""Page "Options de réservation" de Google Flights : prix du même vol site par site
(compagnie, Trip.com, Gotogate, Opodo…).

Cette page est remplie en JavaScript après le chargement : on passe par un vrai
navigateur sans écran (Playwright + Chromium).
- aller simple : URL de réservation construite directement à partir des n° de vol ;
- aller-retour : le retour le moins cher pour l'aller retenu est trouvé côté serveur
  (GoogleFlights.search_returns), puis l'URL de réservation est construite pour les deux vols.
"""

import logging
import re

from .gflights import CONSENT_COOKIE, GoogleFlights
from .links import booking_url

log = logging.getLogger("tracker")

PRICE_RE = re.compile(r"^(\d[\d\s  ]*)\s?€$")


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

    def read(self, url) -> list[dict]:
        """Lit les prix par site sur une page de réservation Google Flights."""
        page = self._page
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_function(
            "() => !document.body.innerText.includes('Récupération des prix')"
            " && document.body.innerText.includes('Réserver avec')",
            timeout=45000,
        )
        return parse_options(page.inner_text("body"))

    def options(self, segments, currency="EUR") -> tuple[list[dict], str]:
        url = booking_url(segments, currency=currency)
        return self.read(url), url


def attach_booking_options(legs: list[dict], currency="EUR") -> None:
    """Ajoute leg["booking"] (prix par site) à chaque vol de la combinaison."""
    todo = [l for l in legs if l.get("segments")]
    if not todo:
        return
    try:
        with BookingBrowser() as b:
            for leg in todo:
                try:
                    if leg["search"].startswith("RT "):
                        # Retour choisi côté serveur (le moins cher pour cet aller), puis page de réservation
                        rets = GoogleFlights(currency).search_returns(leg["query"], leg["segments"]).offers
                        if not rets:
                            raise RuntimeError("aucun vol retour pour cet aller")
                        ret = min(rets, key=lambda o: o.price)
                        leg["return_flight"] = f"retour {ret.depart[-5:]} · {', '.join(ret.airlines)}"
                        leg["return_segments"] = ret.segments
                        url = booking_url(leg["segments"], ret.segments, currency=currency)
                        opts = b.read(url)
                    else:
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
            n = len(dearer)
            what = "agence" if not any(o["airline"] for o in dearer) else "offre"
            parts.append(f"{n} {what}{'s' if n > 1 else ''} plus chère{'s' if n > 1 else ''} (dès {dearer[0]['price']} €)")
    return " · ".join(parts)

