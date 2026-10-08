"""Liens de réservation.

- Google Flights « Options de réservation » d'un vol précis : liste tous les sites qui
  le vendent (compagnie, Trip.com, Gotogate, Opodo…) avec leur prix.
- Recherches équivalentes sur Trip.com, Kayak et Skyscanner.
"""

from base64 import urlsafe_b64encode
from datetime import date

from .gflights import _field, _segment_field, _varint

BOOKING_URL = "https://www.google.com/travel/flights/booking"
NO_PRICE_LIMIT = b"\x82\x01" + _varint(11) + b"\x08" + _varint(2**64 - 1)  # champ 16 {1: max}, comme Google


def _airport(tag: int, code: str) -> bytes:
    return _field(tag, b"\x08\x01" + _field(0x12, code.encode()))


def booking_url(*flights, currency="EUR", language="fr") -> str:
    """Page de réservation Google pour un aller simple (1 vol) ou un aller-retour (2 vols).
    Chaque vol = liste de segments (départ, date, arrivée, compagnie, n° de vol)."""
    raw = b"\x08\x1c\x10\x02"
    for segs in flights:
        leg = _field(0x12, segs[0][1].encode()) + b"".join(_segment_field(*sg) for sg in segs)
        leg += b"\x28\x01" + _airport(0x6A, segs[0][0]) + _airport(0x72, segs[-1][2])
        raw += _field(0x1A, leg)
    trip = 2 if len(flights) == 1 else 1  # 2 = aller simple, 1 = aller-retour
    raw += b"\x40\x01\x48\x01\x70\x01" + NO_PRICE_LIMIT + b"\x98\x01" + _varint(trip)
    tfs = urlsafe_b64encode(raw).decode().rstrip("=")
    return f"{BOOKING_URL}?tfs={tfs}&hl={language}&gl=FR&curr={currency}"


# Codes « toutes les villes » propres à chaque site
_SKYSCANNER_CITY = {"CDG+ORY": "pari", "SEL": "sela", "TYO": "tyoa", "OSA": "osaa", "LON": "lond",
                    "NYC": "nyca", "MIL": "mila", "ROM": "rome", "STO": "stoc", "CHI": "chia",
                    "WAS": "wasa", "BJS": "bjsa", "SHA": "csha", "YTO": "ytoa", "SAO": "saoa",
                    "RIO": "rioa", "BUE": "buea", "JKT": "jkta"}
_TRIP_CITY = {"CDG+ORY": "par"}


def _first(code: str) -> str:
    return code.split("+")[0]


def partner_links(origin: str, destination: str, depart: str, ret: str | None = None, adults: int = 1) -> dict:
    """Recherches équivalentes chez les comparateurs / agences (même trajet, mêmes dates)."""
    yymmdd = lambda d: date.fromisoformat(d).strftime("%y%m%d")  # noqa: E731
    kayak = f"https://www.kayak.fr/flights/{origin.replace('+', ',')}-{destination.replace('+', ',')}/{depart}"
    kayak += (f"/{ret}" if ret else "") + (f"/{adults}adults" if adults > 1 else "") + "?sort=price_a"

    sky_o = _SKYSCANNER_CITY.get(origin, _first(origin).lower())
    sky_d = _SKYSCANNER_CITY.get(destination, _first(destination).lower())
    sky = f"https://www.skyscanner.fr/transport/vols/{sky_o}/{sky_d}/{yymmdd(depart)}/" + (f"{yymmdd(ret)}/" if ret else "")
    sky += f"?adultsv2={adults}&cabinclass=economy"

    t_o = _TRIP_CITY.get(origin, _first(origin).lower())
    t_d = _TRIP_CITY.get(destination, _first(destination).lower())
    trip = (f"https://fr.trip.com/flights/showfarefirst?dcity={t_o}&acity={t_d}&ddate={depart}"
            + (f"&rdate={ret}&triptype=rt" if ret else "&triptype=ow")
            + f"&class=y&quantity={adults}&locale=fr-FR&curr=EUR")
    return {"trip": trip, "kayak": kayak, "skyscanner": sky}
