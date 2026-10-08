"""Génère tracker/places.py : destinations de l'onglet Explorer (avec coordonnées).

Usage : python -I scripts/build_places.py <chemin/airports.csv OurAirports>
"""

import csv
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tracker" / "places.py"

# (code Google Flights, aéroport principal pour les coordonnées, ville, pays ISO, région)
PLACES = [
    # Europe
    ("LIS", "LIS", "Lisbonne", "PT", "europe"), ("OPO", "OPO", "Porto", "PT", "europe"), ("FAO", "FAO", "Faro", "PT", "europe"),
    ("BCN", "BCN", "Barcelone", "ES", "europe"), ("MAD", "MAD", "Madrid", "ES", "europe"), ("SVQ", "SVQ", "Séville", "ES", "europe"),
    ("VLC", "VLC", "Valence", "ES", "europe"), ("AGP", "AGP", "Malaga", "ES", "europe"), ("PMI", "PMI", "Majorque", "ES", "europe"),
    ("IBZ", "IBZ", "Ibiza", "ES", "europe"), ("ROM", "FCO", "Rome", "IT", "europe"), ("MIL", "MXP", "Milan", "IT", "europe"),
    ("VCE", "VCE", "Venise", "IT", "europe"), ("NAP", "NAP", "Naples", "IT", "europe"), ("CTA", "CTA", "Catane", "IT", "europe"),
    ("ATH", "ATH", "Athènes", "GR", "europe"), ("HER", "HER", "Héraklion (Crète)", "GR", "europe"), ("JTR", "JTR", "Santorin", "GR", "europe"),
    ("LON", "LHR", "Londres", "GB", "europe"), ("EDI", "EDI", "Édimbourg", "GB", "europe"), ("DUB", "DUB", "Dublin", "IE", "europe"),
    ("AMS", "AMS", "Amsterdam", "NL", "europe"), ("BER", "BER", "Berlin", "DE", "europe"), ("MUC", "MUC", "Munich", "DE", "europe"),
    ("PRG", "PRG", "Prague", "CZ", "europe"), ("BUD", "BUD", "Budapest", "HU", "europe"), ("VIE", "VIE", "Vienne", "AT", "europe"),
    ("KRK", "KRK", "Cracovie", "PL", "europe"), ("WAW", "WAW", "Varsovie", "PL", "europe"), ("CPH", "CPH", "Copenhague", "DK", "europe"),
    ("STO", "ARN", "Stockholm", "SE", "europe"), ("OSL", "OSL", "Oslo", "NO", "europe"), ("HEL", "HEL", "Helsinki", "FI", "europe"),
    ("SPU", "SPU", "Split", "HR", "europe"), ("DBV", "DBV", "Dubrovnik", "HR", "europe"), ("MLA", "MLA", "Malte", "MT", "europe"),
    ("IST", "IST", "Istanbul", "TR", "europe"), ("LCA", "LCA", "Larnaca (Chypre)", "CY", "europe"), ("NCE", "NCE", "Nice", "FR", "europe"),
    ("AJA", "AJA", "Ajaccio", "FR", "europe"), ("REK", "KEF", "Reykjavik", "IS", "europe"),
    # Afrique du Nord / Moyen-Orient (moyen-courrier)
    ("RAK", "RAK", "Marrakech", "MA", "europe"), ("CMN", "CMN", "Casablanca", "MA", "europe"), ("TUN", "TUN", "Tunis", "TN", "europe"),
    ("ALG", "ALG", "Alger", "DZ", "europe"), ("CAI", "CAI", "Le Caire", "EG", "europe"), ("TLV", "TLV", "Tel Aviv", "IL", "europe"),
    # Long-courrier
    ("NYC", "JFK", "New York", "US", "long"), ("YMQ", "YUL", "Montréal", "CA", "long"), ("LAX", "LAX", "Los Angeles", "US", "long"),
    ("SFO", "SFO", "San Francisco", "US", "long"), ("MIA", "MIA", "Miami", "US", "long"), ("MEX", "MEX", "Mexico", "MX", "long"),
    ("CUN", "CUN", "Cancún", "MX", "long"), ("HAV", "HAV", "La Havane", "CU", "long"), ("PUJ", "PUJ", "Punta Cana", "DO", "long"),
    ("BOG", "BOG", "Bogota", "CO", "long"), ("LIM", "LIM", "Lima", "PE", "long"), ("RIO", "GIG", "Rio de Janeiro", "BR", "long"),
    ("BUE", "EZE", "Buenos Aires", "AR", "long"), ("DXB", "DXB", "Dubaï", "AE", "long"), ("MLE", "MLE", "Maldives", "MV", "long"),
    ("CMB", "CMB", "Colombo", "LK", "long"), ("DEL", "DEL", "Delhi", "IN", "long"), ("BKK", "BKK", "Bangkok", "TH", "long"),
    ("HKT", "HKT", "Phuket", "TH", "long"), ("SIN", "SIN", "Singapour", "SG", "long"), ("KUL", "KUL", "Kuala Lumpur", "MY", "long"),
    ("DPS", "DPS", "Bali", "ID", "long"), ("HAN", "HAN", "Hanoï", "VN", "long"), ("SGN", "SGN", "Hô Chi Minh", "VN", "long"),
    ("HKG", "HKG", "Hong Kong", "HK", "long"), ("TPE", "TPE", "Taïpei", "TW", "long"), ("SEL", "ICN", "Séoul", "KR", "long"),
    ("TYO", "HND", "Tokyo", "JP", "long"), ("OSA", "KIX", "Osaka", "JP", "long"), ("SYD", "SYD", "Sydney", "AU", "long"),
    ("CPT", "CPT", "Le Cap", "ZA", "long"), ("NBO", "NBO", "Nairobi", "KE", "long"), ("ZNZ", "ZNZ", "Zanzibar", "TZ", "long"),
    ("DSS", "DSS", "Dakar", "SN", "long"), ("MRU", "MRU", "Maurice", "MU", "long"), ("RUN", "RUN", "La Réunion", "RE", "long"),
    ("PTP", "PTP", "Guadeloupe", "GP", "long"), ("FDF", "FDF", "Martinique", "MQ", "long"), ("PPT", "PPT", "Tahiti", "PF", "long"),
]


def main(src):
    coords = {}
    with open(src, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("iata_code"):
                coords[r["iata_code"].upper()] = (round(float(r["latitude_deg"]), 3), round(float(r["longitude_deg"]), 3))
    rows, missing = [], []
    for code, ap, city, country, region in PLACES:
        if ap not in coords:
            missing.append(ap)
            continue
        lat, lon = coords[ap]
        rows.append(f"    ({code!r}, {city!r}, {country!r}, {region!r}, {lat}, {lon}),")
    OUT.write_text(
        '"""Destinations de l\'onglet Explorer et des bons plans (généré par scripts/build_places.py)."""\n\n'
        "# (code Google Flights, ville, pays ISO, région, latitude, longitude)\nPLACES = [\n" + "\n".join(rows) + "\n]\n",
        encoding="utf-8",
    )
    print(len(rows), "destinations ; coordonnées manquantes :", missing)


if __name__ == "__main__":
    main(sys.argv[1])
