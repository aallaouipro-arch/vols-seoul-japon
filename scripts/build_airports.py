"""Génère app/public/airports.json (autocomplétion) à partir du CSV OurAirports.

Usage : python -I scripts/build_airports.py <chemin/airports.csv>
Source : https://davidmegginson.github.io/ourairports-data/airports.csv (domaine public)
Format de sortie : [[code, nom, ville, pays ISO, rang, alias], ...]
  rang 3 = toutes les villes (plusieurs aéroports), 2 = grand aéroport, 1 = moyen.
"""

import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "public" / "airports.json"

# Villes à plusieurs aéroports : code envoyé à Google Flights (code ville IATA ou aéroports joints par "+")
CITIES = [
    ("CDG+ORY", "Paris (CDG + Orly)", "Paris", "FR"),  # sans Beauvais
    ("SEL", "Séoul (Incheon + Gimpo)", "Séoul", "KR"),
    ("TYO", "Tokyo (Haneda + Narita)", "Tokyo", "JP"),
    ("OSA", "Osaka (Kansai + Itami)", "Osaka", "JP"),
    ("LON", "Londres (tous les aéroports)", "Londres", "GB"),
    ("NYC", "New York (tous les aéroports)", "New York", "US"),
    ("MIL", "Milan (tous les aéroports)", "Milan", "IT"),
    ("ROM", "Rome (tous les aéroports)", "Rome", "IT"),
    ("STO", "Stockholm (tous les aéroports)", "Stockholm", "SE"),
    ("CHI", "Chicago (tous les aéroports)", "Chicago", "US"),
    ("WAS", "Washington (tous les aéroports)", "Washington", "US"),
    ("BJS", "Pékin (tous les aéroports)", "Pékin", "CN"),
    ("SHA", "Shanghai (tous les aéroports)", "Shanghai", "CN"),
    ("YTO", "Toronto (tous les aéroports)", "Toronto", "CA"),
    ("SAO", "São Paulo (tous les aéroports)", "São Paulo", "BR"),
    ("RIO", "Rio de Janeiro (tous les aéroports)", "Rio de Janeiro", "BR"),
    ("BUE", "Buenos Aires (tous les aéroports)", "Buenos Aires", "AR"),
    ("JKT", "Jakarta (tous les aéroports)", "Jakarta", "ID"),
]

# Noms français → nom anglais utilisé par OurAirports (sert d'alias de recherche)
FR = {
    "Seoul": "Séoul", "Beijing": "Pékin", "London": "Londres", "Moscow": "Moscou", "Warsaw": "Varsovie",
    "Venice": "Venise", "Florence": "Florence", "Naples": "Naples", "Lisbon": "Lisbonne",
    "Copenhagen": "Copenhague", "Athens": "Athènes", "Cairo": "Le Caire", "Mumbai": "Bombay",
    "Cape Town": "Le Cap", "Guangzhou": "Canton", "Singapore": "Singapour", "Hanoi": "Hanoï",
    "Ho Chi Minh City": "Hô Chi Minh", "Seville": "Séville", "Barcelona": "Barcelone",
    "Brussels": "Bruxelles", "Geneva": "Genève", "Vienna": "Vienne", "Frankfurt": "Francfort",
    "Frankfurt am Main": "Francfort", "Hamburg": "Hambourg", "Edinburgh": "Édimbourg",
    "Bucharest": "Bucarest", "Marrakesh": "Marrakech", "Algiers": "Alger", "Mexico City": "Mexico",
    "Montreal": "Montréal", "Quebec": "Québec", "New Orleans": "La Nouvelle-Orléans",
    "Rome": "Rome", "Milan": "Milan", "Munich": "Munich", "Cologne": "Cologne", "Prague": "Prague",
    "Krakow": "Cracovie", "Kraków": "Cracovie", "Saint Petersburg": "Saint-Pétersbourg",
    "Taipei": "Taïpei", "Busan": "Pusan", "Jeju": "Jeju", "Kyoto": "Kyoto", "Sapporo": "Sapporo",
    "Fukuoka": "Fukuoka", "Okinawa": "Okinawa", "Nagoya": "Nagoya", "Dubai": "Dubaï", "Doha": "Doha",
    "Istanbul": "Istanbul", "Tel Aviv": "Tel Aviv", "Malta": "Malte", "Valletta": "La Valette",
}


def main(src: str):
    rows = []
    for c in CITIES:
        rows.append([c[0], c[1], c[2], c[3], 3, ""])
    seen = set()
    with open(src, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("iata_code") or "").strip().upper()
            if (
                len(code) != 3
                or not code.isalpha()
                or code in seen
                or r.get("scheduled_service") != "yes"
                or r.get("type") not in ("large_airport", "medium_airport")
            ):
                continue
            seen.add(code)
            city = (r.get("municipality") or "").strip()
            alias = FR.get(city, "")
            rank = 2 if r["type"] == "large_airport" else 1
            rows.append([code, r["name"].strip(), alias or city, r["iso_country"], rank, city if alias else ""])
    rows.sort(key=lambda x: (-x[4], x[2]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rows)} entrées -> {OUT} ({OUT.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main(sys.argv[1])
