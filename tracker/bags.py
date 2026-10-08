"""Coût des valises en soute (23 kg) selon la compagnie.

Google Flights ne donne pas les frais de bagages en soute (en France, son filtre « Bagages »
ne gère que le bagage à main) : on les estime à partir du tarif le moins cher de chaque
compagnie, repérée par son code IATA (les noms affichés varient : « JAL », « THAI »…).
Valeurs indicatives 2026. En cas de doute, hypothèse prudente : aucune valise incluse
(le prix affiché peut être un peu trop haut, jamais trompeusement bas).
"""

from dataclasses import dataclass


@dataclass
class BagRule:
    included: int  # valises 23 kg incluses dans le tarif le moins cher
    fee: int  # € par valise supplémentaire, par trajet
    note: str = ""


def _r(included, fee, note):
    return BagRule(included, fee, note)


# Long-courrier (vol de 6 h et plus)
LONG_HAUL = {
    # Europe « Light » : aucune valise
    "AF": _r(0, 90, "Air France Light : bagage cabine seul"),
    "KL": _r(0, 90, "KLM Light : bagage cabine seul"),
    "LH": _r(0, 80, "Lufthansa Economy Light : valise payante"),
    "VL": _r(0, 80, "groupe Lufthansa, tarif Light"),
    "EN": _r(0, 80, "groupe Lufthansa, tarif Light"),
    "4Y": _r(0, 80, "Discover (groupe Lufthansa), tarif Light"),
    "LX": _r(0, 80, "SWISS Light : bagage cabine seul"),
    "OS": _r(0, 80, "Austrian Light : bagage cabine seul"),
    "SN": _r(0, 80, "Brussels Airlines Light"),
    "AY": _r(0, 80, "Finnair Light : bagage cabine seul"),
    "BA": _r(0, 80, "British Airways Basic : bagage cabine seul"),
    "IB": _r(0, 75, "Iberia Basic : bagage cabine seul"),
    "UX": _r(0, 70, "Air Europa Lite : bagage cabine seul"),
    "AZ": _r(0, 75, "ITA Light : bagage cabine seul"),
    "TP": _r(0, 75, "TAP Discount : à vérifier"),
    "AT": _r(0, 80, "Royal Air Maroc Basic : à vérifier"),
    "AC": _r(0, 80, "Air Canada Basic : bagage cabine seul"),
    "TS": _r(0, 80, "Air Transat Eco : à vérifier"),
    "AA": _r(0, 90, "American Basic : à vérifier"),
    "DL": _r(0, 90, "Delta Basic : à vérifier"),
    "UA": _r(0, 90, "United Basic : à vérifier"),
    "B6": _r(0, 90, "JetBlue Blue Basic : à vérifier"),
    "DE": _r(0, 70, "Condor Economy Light"),
    "SS": _r(0, 80, "Corsair : à vérifier"),
    "TX": _r(0, 80, "Air Caraïbes Soft : à vérifier"),
    "BF": _r(0, 60, "French bee Basic : bagage cabine seul"),
    "UU": _r(0, 80, "Air Austral : à vérifier"),
    "SB": _r(0, 80, "Aircalin : à vérifier"),
    "PC": _r(0, 50, "Pegasus (low-cost) : valise payante"),
    "VF": _r(0, 50, "AJet (low-cost) : valise payante"),
    "ZG": _r(0, 45, "ZIPAIR (low-cost) : valise payante"),
    # Asie / Moyen-Orient : en général 1 valise incluse
    "KE": _r(1, 150, "Korean Air : 1×23 kg"),
    "OZ": _r(1, 150, "Asiana : 1×23 kg"),
    "JL": _r(2, 0, "JAL : 2×23 kg inclus"),
    "NH": _r(1, 120, "ANA : 1×23 kg sur le tarif le moins cher"),
    "CZ": _r(1, 100, "China Southern : 1×23 kg"),
    "CA": _r(1, 100, "Air China : 1×23 kg"),
    "MU": _r(1, 100, "China Eastern : 1×23 kg"),
    "CX": _r(1, 120, "Cathay Pacific : 1×23 kg"),
    "BR": _r(1, 120, "EVA Air : 1×23 kg"),
    "SQ": _r(1, 120, "Singapore Airlines Lite : 25 kg"),
    "TG": _r(1, 120, "THAI : 1×23 kg"),
    "VN": _r(1, 100, "Vietnam Airlines : 1×23 kg"),
    "MH": _r(1, 100, "Malaysia Airlines : 1×23 kg"),
    "QR": _r(1, 150, "Qatar : 25 kg en Economy Classic"),
    "EK": _r(1, 150, "Emirates : 25 kg en Economy Saver"),
    "EY": _r(1, 150, "Etihad : 23 kg (à vérifier selon tarif)"),
    "GF": _r(1, 100, "Gulf Air : 1×23 kg"),
    "TK": _r(1, 120, "Turkish : 23 kg en EcoFly"),
    "LO": _r(1, 100, "LOT : 1×23 kg en long-courrier"),
    "JU": _r(1, 80, "Air Serbia : à vérifier"),
    "ET": _r(1, 100, "Ethiopian : à vérifier"),
    "YP": _r(1, 100, "Air Premia : 1×23 kg"),
    "B0": _r(2, 0, "La Compagnie (classe affaires) : 2 valises"),
}

# Court / moyen-courrier
SHORT_HAUL = {
    "U2": _r(0, 35, "easyJet : valise payante"),
    "EW": _r(0, 40, "Eurowings Basic : valise payante"),
    "A5": _r(0, 35, "HOP! (Air France) Light"),
    "WA": _r(0, 35, "KLM Cityhopper Light"),
    "CJ": _r(0, 40, "BA CityFlyer Basic"),
    "VL": _r(0, 40, "Lufthansa City Airlines Light"),
    "EN": _r(0, 40, "Air Dolomiti Light"),
    "TO": _r(0, 35, "Transavia : valise payante"),
    "VY": _r(0, 35, "Vueling Basic : valise payante"),
    "FR": _r(0, 40, "Ryanair : valise payante"),
    "W6": _r(0, 40, "Wizz Air : valise payante"),
    "TB": _r(0, 35, "TUI fly : à vérifier"),
    "PC": _r(0, 35, "Pegasus : valise payante"),
    "VF": _r(0, 35, "AJet : valise payante"),
    "AF": _r(0, 35, "Air France Light : bagage cabine seul"),
    "KL": _r(0, 35, "KLM Light : bagage cabine seul"),
    "LH": _r(0, 40, "Lufthansa Light"),
    "LX": _r(0, 40, "SWISS Light"),
    "OS": _r(0, 40, "Austrian Light"),
    "SN": _r(0, 40, "Brussels Airlines Light"),
    "BA": _r(0, 40, "British Airways Basic"),
    "IB": _r(0, 40, "Iberia Basic"),
    "AZ": _r(0, 40, "ITA Light"),
    "TP": _r(0, 40, "TAP Discount"),
    "AT": _r(0, 40, "Royal Air Maroc Basic"),
    "A3": _r(0, 40, "Aegean Light"),
    "SK": _r(0, 40, "SAS Go Light"),
    "EI": _r(0, 40, "Aer Lingus Saver"),
    "LO": _r(0, 40, "LOT Saver court-courrier"),
    "TK": _r(1, 50, "Turkish EcoFly : 20-23 kg"),
    "ET": _r(0, 50, "Ethiopian : à vérifier"),
    # Asie du Nord-Est (Séoul ⇄ Japon)
    "ZG": _r(0, 25, "ZIPAIR : valise ~25 €"),
    "MM": _r(0, 30, "Peach : valise payante"),
    "GK": _r(0, 30, "Jetstar Japan : valise payante"),
    "7C": _r(0, 35, "Jeju Air : valise payante"),
    "TW": _r(0, 35, "t'way : valise payante"),
    "LJ": _r(0, 35, "Jin Air : valise payante"),
    "BX": _r(0, 35, "Air Busan : valise payante"),
    "RS": _r(0, 35, "Air Seoul : valise payante"),
    "ZE": _r(0, 35, "Eastar Jet : valise payante"),
    "RF": _r(0, 35, "Aero K : valise payante"),
    "KE": _r(1, 60, "Korean Air : 1×23 kg"),
    "OZ": _r(1, 60, "Asiana : 1×23 kg"),
    "JL": _r(2, 0, "JAL : 2×23 kg"),
    "NH": _r(2, 0, "ANA : 2×23 kg"),
    "YP": _r(1, 50, "Air Premia : 1×23 kg"),
}

# Compagnies dont le tarif le moins cher inclut au moins une valise en long-courrier : une
# recherche dédiée les fait remonter (elles ne sont pas toujours sur la 1re page de Google)
BAG_INCLUDED_CARRIERS = sorted({c for c, r in LONG_HAUL.items() if r.included >= 1} - {"B0"})

# Pages « bagages » officielles quand Google ne les fournit pas
BAG_POLICY_FALLBACK = {
    "ZG": "https://www.zipair.net/en/service/baggage",
}

# Compagnies low-cost asiatiques qui facturent dans la devise du pays de départ
LOCAL_CURRENCY = {"ZG", "MM", "GK", "7C", "TW", "LJ", "BX", "RS", "ZE", "RF"}

DEFAULT_LONG = BagRule(0, 90, "compagnie non répertoriée : on suppose aucune valise incluse")
DEFAULT_SHORT = BagRule(0, 40, "compagnie non répertoriée : on suppose aucune valise incluse")


def rule_for(airlines: list[str], duration_min: int, code: str | None = None) -> BagRule:
    long_haul = duration_min >= 6 * 60
    table = LONG_HAUL if long_haul else SHORT_HAUL
    if code and code in table:
        return table[code]
    return DEFAULT_LONG if long_haul else DEFAULT_SHORT


def bag_cost(airlines: list[str], duration_min: int, bags_per_direction: list[int], code: str | None = None) -> tuple[int, str]:
    """Supplément valises pour un vol (1 sens = [n], A/R = [n_aller, n_retour])."""
    rule = rule_for(airlines, duration_min, code)
    extra = sum(max(0, n - rule.included) for n in bags_per_direction) * rule.fee
    return extra, rule.note
