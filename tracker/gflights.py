"""Requêtes Google Flights.

On réutilise l'encodeur protobuf `tfs` de fast-flights, mais on fait la requête
et le parsing nous-mêmes : la lib ne gère ni la page de consentement RGPD servie
aux IP européennes, ni les "Price insights" (fourchette habituelle + historique).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from base64 import b64encode

from fast_flights import FlightQuery, Passengers, create_query
from fast_flights.pb.flights_pb2 import Airport
from primp import Client
from selectolax.lexbor import LexborHTMLParser

logging.getLogger("primp").setLevel(logging.WARNING)  # sinon 1 ligne INFO par requête

URL = "https://www.google.com/travel/flights"
# Cookie "Tout accepter" : sans lui Google redirige vers consent.google.com
CONSENT_COOKIE = "SOCS=CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiAo_CmBg; CONSENT=YES+cb"


class GoogleFlightsError(Exception):
    pass


@dataclass
class Offer:
    price: int
    airlines: list[str]
    route: str  # ex. "CDG-ZRH-ICN"
    depart: str  # ex. "2027-07-23 09:45"
    arrive: str
    duration_min: int
    stops: int
    # (départ, date, arrivée, code compagnie, n° de vol) par segment : sert à ouvrir
    # la page "Options de réservation" de ce vol précis
    segments: list[tuple[str, str, str, str, str]] = field(default_factory=list)


@dataclass
class Insights:
    """Bloc "Price insights" de Google Flights (payload[5])."""

    current: int | None
    typical_low: int | None
    typical_high: int | None
    history: list[tuple[str, int]] = field(default_factory=list)  # (date ISO, prix)

    @property
    def level(self) -> str:
        if self.current is None or self.typical_low is None or self.typical_high is None:
            return "inconnu"
        if self.current < self.typical_low:
            return "bas"
        if self.current > self.typical_high:
            return "élevé"
        return "habituel"


@dataclass
class SearchResult:
    offers: list[Offer]
    insights: Insights | None
    url: str

    @property
    def best(self) -> Offer | None:
        return min(self.offers, key=lambda o: o.price, default=None)


def _hm(t) -> str:
    t = [*(t or []), None, None]
    return f"{t[0] or 0:02d}:{t[1] or 0:02d}"


def _ymd(d) -> str:
    return f"{d[0]:04d}-{d[1]:02d}-{d[2]:02d}"


def _price(v) -> int | None:
    return v[1] if isinstance(v, list) and len(v) > 1 else None


def _parse_offer(k) -> Offer | None:
    try:
        price = k[1][0][1]
    except (IndexError, TypeError):
        return None  # vol listé sans prix
    f = k[0]
    segs = f[2]
    route = "-".join([segs[0][3], *(s[6] for s in segs)])
    return Offer(
        price=price,
        airlines=list(f[1] or []),
        route=route,
        depart=f"{_ymd(f[4])} {_hm(f[5])}",
        arrive=f"{_ymd(f[7])} {_hm(f[8])}",
        duration_min=f[9] or 0,
        stops=len(segs) - 1,
        segments=[_segment(sg) for sg in segs],
    )


def _segment(sg) -> tuple[str, str, str, str, str]:
    try:
        return (sg[3], _ymd(sg[20]), sg[6], sg[22][0], sg[22][1])
    except (IndexError, TypeError):
        return (sg[3], "", sg[6], "", "")


def _parse_insights(pi) -> Insights | None:
    if not pi:
        return None
    history = []
    try:
        for ts, price in pi[10][0]:
            day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
            history.append((day, price))
    except (IndexError, TypeError):
        pass
    return Insights(
        current=_price(pi[1]),
        typical_low=_price(pi[4]),
        typical_high=_price(pi[5]),
        history=history,
    )


def parse_payload(html: str) -> tuple[list[Offer], Insights | None]:
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise GoogleFlightsError("payload ds:1 absent (page de consentement ou blocage ?)")
    data = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        raise GoogleFlightsError("Google a renvoyé une erreur pour cette recherche")
    payload = json.loads(data)

    offers = []
    for block in (payload[2], payload[3]):  # "meilleurs vols" puis "autres vols"
        for k in (block or [[]])[0] or []:
            if (o := _parse_offer(k)) is not None:
                offers.append(o)
    return offers, _parse_insights(payload[5] if len(payload) > 5 else None)


class GoogleFlights:
    def __init__(self, currency="EUR", language="fr", adults=1, max_stops=None):
        self.currency = currency
        self.language = language
        self.adults = adults
        self.max_stops = max_stops
        self.client = Client(
            impersonate="chrome_145",
            impersonate_os="macos",
            referer=True,
            cookie_store=False,
            headers={"Cookie": CONSENT_COOKIE},
            timeout=30,
        )

    def search(self, legs: list[tuple[str, str, str]], max_stops: int | None = -1) -> SearchResult:
        """legs = [(date, origine, destination)] ; 1 leg = aller simple, 2 legs = aller-retour.

        Origine / destination : code IATA, ou plusieurs séparés par "+" (ex. "CDG+ORY").
        max_stops : 0 = direct, 1 = une escale max, None = illimité, -1 = valeur par défaut du client.
        """
        if len(legs) not in (1, 2):
            raise ValueError("seuls l'aller simple et l'aller-retour sont supportés")
        tfs = _encode_tfs(
            legs,
            trip="one-way" if len(legs) == 1 else "round-trip",
            adults=self.adults,
            max_stops=self.max_stops if max_stops == -1 else max_stops,
        )
        # gl=FR : point de vente France (prix identiques même lancé depuis un serveur à l'étranger)
        params = {"tfs": tfs, "hl": self.language, "curr": self.currency, "gl": "FR"}
        res = self.client.get(URL, params=params)
        if res.status_code != 200:
            raise GoogleFlightsError(f"HTTP {res.status_code}")
        offers, insights = parse_payload(res.text)
        url = f"https://www.google.com/travel/flights/search?tfs={tfs}&hl={self.language}&curr={self.currency}&gl=FR"
        return SearchResult(offers=offers, insights=insights, url=url)


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(tag: int, payload: bytes) -> bytes:
    return bytes([tag]) + _varint(len(payload)) + payload


def _encode_tfs(legs, trip, adults, max_stops) -> str:
    """Encode la requête `tfs`. Le protobuf de fast-flights n'accepte qu'un aéroport
    par champ, alors que Google en accepte plusieurs (champ répété) : on ajoute
    les aéroports supplémentaires à la main (champ 13 = départ, 14 = arrivée)."""
    q = create_query(
        flights=[FlightQuery(date=d, from_airport=a.split("+")[0], to_airport=b.split("+")[0]) for d, a, b in legs],
        trip=trip,
        passengers=Passengers(adults=adults),
        max_stops=max_stops,
    )
    info = q.pb()
    flight_data = list(info.data)
    del info.data[:]
    raw = info.SerializeToString()
    for fd, (_, a, b) in zip(flight_data, legs):
        extra = b"".join(_field(0x6A, Airport(airport=x).SerializeToString()) for x in a.split("+")[1:])
        extra += b"".join(_field(0x72, Airport(airport=x).SerializeToString()) for x in b.split("+")[1:])
        raw += _field(0x1A, fd.SerializeToString() + extra)
    return b64encode(raw).decode()
