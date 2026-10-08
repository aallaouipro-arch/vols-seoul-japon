"""Requêtes Google Flights.

On réutilise l'encodeur protobuf `tfs` de fast-flights, mais on fait la requête
et le parsing nous-mêmes : la lib ne gère ni la page de consentement RGPD servie
aux IP européennes, ni les "Price insights" (fourchette habituelle + historique).
"""

import json
import logging
import time
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
    layovers: list[tuple[str, int, str]] = field(default_factory=list)  # (aéroport, minutes, ville)
    co2_kg: int | None = None  # émissions estimées du vol
    co2_diff_pct: int | None = None  # écart par rapport aux émissions habituelles du trajet

    @property
    def airline_code(self) -> str:
        return self.segments[0][3] if self.segments else ""


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
    bag_links: dict[str, str] = field(default_factory=dict)  # code compagnie → page « bagages » officielle

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
        layovers=_layovers(f[13] if len(f) > 13 else None),
        **_emissions(f[22] if len(f) > 22 else None),
    )


def _emissions(raw) -> dict:
    try:
        return {"co2_kg": round(raw[7] / 1000) if raw[7] else None, "co2_diff_pct": raw[3]}
    except (IndexError, TypeError):
        return {}


def _layovers(raw) -> list[tuple[str, int, str]]:
    out = []
    for l in raw or []:
        try:
            out.append((l[1], l[0] or 0, l[5] or l[4] or l[1]))
        except (IndexError, TypeError):
            continue
    return out


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
    offers, insights, _ = parse_full(html)
    return offers, insights


def parse_full(html: str) -> tuple[list[Offer], Insights | None, dict[str, str]]:
    """Vols + Price insights + liens vers la politique bagages de chaque compagnie (payload[11])."""
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
    bag_links = {}
    for row in (payload[11] if len(payload) > 11 and payload[11] else []):
        if isinstance(row, list) and len(row) > 2 and row[0] and row[2]:
            bag_links[row[0]] = row[2]
    return offers, _parse_insights(payload[5] if len(payload) > 5 else None), bag_links


class SearchOptions:
    """Options d'une recherche (toutes transmises à Google Flights dans `tfs`)."""

    SEATS = ("economy", "premium-economy", "business", "first")

    def __init__(self, adults=1, children=0, infants_seat=0, infants_lap=0, seat="economy", max_stops=1,
                 airlines=None, dep_hours=None, arr_hours=None, ret_dep_hours=None, max_duration=None,
                 max_price=None, less_emissions=False):
        self.adults, self.children, self.infants_seat, self.infants_lap = adults, children, infants_seat, infants_lap
        self.seat = seat if seat in self.SEATS else "economy"
        self.max_stops = max_stops
        self.airlines = airlines
        self.dep_hours, self.arr_hours, self.ret_dep_hours = dep_hours, arr_hours, ret_dep_hours
        self.max_duration, self.max_price, self.less_emissions = max_duration, max_price, less_emissions

    @property
    def travelers_with_bags(self) -> int:
        return self.adults + self.children  # les bébés n'ont pas de valise en soute

    def copy(self, **kw) -> "SearchOptions":
        o = SearchOptions.__new__(SearchOptions)
        o.__dict__ = {**self.__dict__, **kw}
        return o


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

    def _opts(self, max_stops, airlines, opts):
        if opts is None:
            opts = SearchOptions(adults=self.adults, max_stops=self.max_stops)
        if max_stops != -1:
            opts = opts.copy(max_stops=max_stops)
        if airlines is not None:
            opts = opts.copy(airlines=airlines)
        return opts

    def _get(self, tfs: str) -> SearchResult:
        # gl=FR : point de vente France (prix identiques même lancé depuis un serveur à l'étranger)
        params = {"tfs": tfs, "hl": self.language, "curr": self.currency, "gl": "FR"}
        last = None
        for attempt in (1, 2):  # Google renvoie parfois une erreur passagère
            try:
                res = self.client.get(URL, params=params)
                if res.status_code != 200:
                    raise GoogleFlightsError(f"HTTP {res.status_code}")
                offers, insights, bag_links = parse_full(res.text)
                url = f"https://www.google.com/travel/flights/search?tfs={tfs}&hl={self.language}&curr={self.currency}&gl=FR"
                return SearchResult(offers=offers, insights=insights, url=url, bag_links=bag_links)
            except GoogleFlightsError as e:
                last = e
                if attempt == 1:
                    time.sleep(0.8)
        raise last

    def search(self, legs: list[tuple[str, str, str]], max_stops: int | None = -1, airlines: list[str] | None = None,
               opts: SearchOptions | None = None) -> SearchResult:
        """legs = [(date, origine, destination)] ; 1 leg = aller simple, 2 legs = aller-retour.

        Origine / destination : code IATA, ou plusieurs séparés par "+" (ex. "CDG+ORY").
        max_stops : 0 = direct, 1 = une escale max, None = illimité, -1 = valeur des options.
        airlines : limiter à ces compagnies / alliances (fait remonter des vols absents de la 1re page).
        """
        if len(legs) not in (1, 2):
            raise ValueError("seuls l'aller simple et l'aller-retour sont supportés")
        o = self._opts(max_stops, airlines, opts)
        return self._get(_encode_tfs(legs, "one-way" if len(legs) == 1 else "round-trip", o))

    def search_returns(self, legs, outbound_segments, max_stops: int | None = -1, opts: SearchOptions | None = None) -> SearchResult:
        """Aller-retour, aller déjà choisi : renvoie les vols retour possibles.
        Le prix de chaque offre est le prix TOTAL de l'aller-retour."""
        o = self._opts(max_stops, None, opts)
        return self._get(_encode_tfs(legs, "round-trip", o, selected=outbound_segments))


def _merge(base: SearchResult, others: list[SearchResult]) -> SearchResult:
    seen = {tuple(map(tuple, o.segments)) for o in base.offers}
    for r in others:
        for o in r.offers:
            k = tuple(map(tuple, o.segments))
            if k not in seen:
                seen.add(k)
                base.offers.append(o)
        base.bag_links = {**r.bag_links, **base.bag_links}
        if base.insights is None:
            base.insights = r.insights
    return base


def search_with_bags(legs, max_stops, carriers: list[str], need_bags: bool, opts: SearchOptions | None = None) -> SearchResult:
    """Recherche normale, complétée (si des valises sont demandées) par une recherche limitée aux
    compagnies qui incluent des valises : leurs vols ne sont pas toujours sur la 1re page de Google."""
    from concurrent.futures import ThreadPoolExecutor

    if not need_bags:
        return GoogleFlights().search(legs, max_stops, opts=opts)
    with ThreadPoolExecutor(max_workers=2) as ex:
        main = ex.submit(GoogleFlights().search, legs, max_stops, None, opts)
        extra = ex.submit(GoogleFlights().search, legs, max_stops, carriers, opts)
        res = main.result()
        try:
            return _merge(res, [extra.result()])
        except Exception:
            return res


ALLIANCES = ["STAR_ALLIANCE", "ONEWORLD", "SKYTEAM"]


def deep_search(legs, opts: SearchOptions, extra_carriers: list[str] | None = None) -> SearchResult:
    """« Afficher plus de vols » : la 1re page de Google ne contient qu'une partie des vols. On découpe
    la recherche (tranches horaires de 2 h à l'aller, alliances, vols directs, compagnies
    supplémentaires) et on fusionne : 2 à 3 fois plus de vols, en ~2 s (requêtes en parallèle)."""
    from concurrent.futures import ThreadPoolExecutor

    parts = [opts]
    if not opts.dep_hours:
        parts += [opts.copy(dep_hours=(h, h + 1)) for h in range(0, 24, 2)]
    if not opts.airlines:
        parts += [opts.copy(airlines=[a], dep_hours=opts.dep_hours or w) for a in ALLIANCES for w in [(0, 11), (12, 23)]]
        if extra_carriers:
            parts.append(opts.copy(airlines=extra_carriers))
    if opts.max_stops != 0:
        parts.append(opts.copy(max_stops=0))

    def run(o):
        try:
            return GoogleFlights().search(legs, -1, None, o)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(run, parts))
    base = next((r for r in results if r), None)
    if base is None:
        raise GoogleFlightsError("aucune réponse de Google Flights")
    return _merge(base, [r for r in results[1:] if r])


def multicity_url(legs, opts: SearchOptions, currency="EUR", language="fr") -> str:
    """Lien Google Flights « multi-destinations » (un seul billet) : le résultat n'est pas lisible
    côté serveur, l'appli compare donc avec des billets séparés et renvoie vers Google."""
    tfs = _encode_tfs(legs, "multi-city", opts)
    return f"https://www.google.com/travel/flights/search?tfs={tfs}&hl={language}&curr={currency}&gl=FR"


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


def _segment_field(frm, date, to, airline, number) -> bytes:
    """Vol précis (champ 4 d'un trajet) : utilisé pour « choisir » un aller ou réserver."""
    enc = lambda tag, t: _field(tag, t.encode())  # noqa: E731
    return _field(0x22, enc(0x0A, frm) + enc(0x12, date) + enc(0x1A, to) + enc(0x2A, airline) + enc(0x32, number))


def _encode_tfs(legs, trip, opts, selected=None, **legacy) -> str:
    """Encode la requête `tfs`. Le protobuf de fast-flights n'accepte qu'un aéroport
    par champ, alors que Google en accepte plusieurs (champ répété) : on ajoute
    les aéroports supplémentaires à la main (champ 13 = départ, 14 = arrivée).
    `selected` : segments du vol aller déjà choisi (affiche alors les retours)."""
    if not isinstance(opts, SearchOptions):  # ancien appel : _encode_tfs(legs, trip, adults=…, max_stops=…)
        opts = SearchOptions(adults=opts or legacy.get("adults", 1), max_stops=legacy.get("max_stops", 1),
                             airlines=legacy.get("airlines"))
    flights = []
    for i, (d, a, b) in enumerate(legs):
        hours = opts.dep_hours if i == 0 else (opts.ret_dep_hours if i == 1 and trip == "round-trip" else None)
        flights.append(FlightQuery(
            date=d, from_airport=a.split("+")[0], to_airport=b.split("+")[0],
            airlines=[c for c in (opts.airlines or []) if c in ALLIANCES] or None,
            earliest_departure_hour=hours[0] if hours else None,
            latest_departure_hour=hours[1] if hours else None,
            earliest_arrival_hour=opts.arr_hours[0] if (opts.arr_hours and i == 0) else None,
            latest_arrival_hour=opts.arr_hours[1] if (opts.arr_hours and i == 0) else None,
            max_duration_minutes=opts.max_duration,
            less_emissions_only=opts.less_emissions,
        ))
    q = create_query(
        flights=flights,
        trip=trip,
        seat=opts.seat,
        passengers=Passengers(adults=opts.adults, children=opts.children,
                              infants_in_seat=opts.infants_seat, infants_on_lap=opts.infants_lap),
        max_stops=opts.max_stops,
        max_price=opts.max_price,
    )
    info = q.pb()
    flight_data = list(info.data)
    del info.data[:]
    raw = info.SerializeToString()
    carriers = [c for c in (opts.airlines or []) if c not in ALLIANCES]
    for i, (fd, (_, a, b)) in enumerate(zip(flight_data, legs)):
        extra = b"".join(_segment_field(*sg) for sg in selected) if (selected and i == 0) else b""
        extra += b"".join(_field(0x6A, Airport(airport=x).SerializeToString()) for x in a.split("+")[1:])
        extra += b"".join(_field(0x72, Airport(airport=x).SerializeToString()) for x in b.split("+")[1:])
        extra += b"".join(_field(0x32, c.encode()) for c in carriers)  # champ 6 : compagnies
        raw += _field(0x1A, fd.SerializeToString() + extra)
    return b64encode(raw).decode()
