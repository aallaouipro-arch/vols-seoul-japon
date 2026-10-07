"""Coût des valises en soute (23 kg) selon la compagnie.

Google Flights ne renvoie pas les frais de bagages dans ses résultats : on les
estime à partir du tarif le moins cher de chaque compagnie (souvent "Light",
sans valise). Valeurs indicatives 2026, à vérifier avant d'acheter.
"""

from dataclasses import dataclass


@dataclass
class BagRule:
    included: int  # valises 23 kg incluses dans le tarif le moins cher
    fee: int  # € par valise supplémentaire, par trajet
    note: str = ""


# Clé = début du nom de compagnie tel qu'affiché par Google Flights (minuscules)
LONG_HAUL = {
    "japan airlines": BagRule(2, 0, "JAL : 2×23 kg inclus en éco"),
    "ana": BagRule(1, 120, "ANA : tarif le moins cher Europe = 1×23 kg"),
    "korean air": BagRule(1, 150, "Korean Air : 1×23 kg vers l'Europe"),
    "asiana": BagRule(1, 150, "Asiana : 1×23 kg vers l'Europe"),
    "china southern": BagRule(1, 100, "China Southern : 1×23 kg (2 en tarif Flex)"),
    "air china": BagRule(1, 100, "Air China : 1×23 kg"),
    "china eastern": BagRule(1, 100, "China Eastern : 1×23 kg"),
    "air france": BagRule(0, 90, "Air France Light long-courrier : bagage cabine seul"),
    "klm": BagRule(0, 90, "KLM Light : bagage cabine seul"),
    "lufthansa": BagRule(0, 80, "Lufthansa Economy Light : valise 65-90 €"),
    "swiss": BagRule(0, 80, "SWISS Light : bagage cabine seul"),
    "austrian": BagRule(0, 80, "Austrian Light : bagage cabine seul"),
    "air dolomiti": BagRule(0, 80, "groupe Lufthansa, Light"),
    "brussels": BagRule(0, 80, "groupe Lufthansa, Light"),
    "finnair": BagRule(0, 80, "Finnair Light : bagage cabine seul"),
    "cathay": BagRule(1, 120, "Cathay : 1×23 kg en Essential (à vérifier)"),
    "qatar": BagRule(1, 150, "Qatar : 25 kg en Economy Classic"),
    "emirates": BagRule(1, 150, "Emirates : 25 kg en Economy Saver"),
    "etihad": BagRule(1, 150, "Etihad : 23 kg (à vérifier selon tarif)"),
    "turkish": BagRule(1, 120, "Turkish : 23 kg en EcoFly"),
    "air premia": BagRule(1, 100, "Air Premia : 1×23 kg"),
}
SHORT_HAUL = {
    "zipair": BagRule(0, 25, "ZIPAIR : valise ~25 € (₩38 100 / ¥4 000)"),
    "peach": BagRule(0, 30, "Peach : valise payante"),
    "jeju air": BagRule(0, 35, "low-cost coréenne"),
    "t'way": BagRule(0, 35, "low-cost coréenne"),
    "jin air": BagRule(0, 35, "low-cost coréenne"),
    "air busan": BagRule(0, 35, "low-cost coréenne"),
    "air seoul": BagRule(0, 35, "low-cost coréenne"),
    "eastar": BagRule(0, 35, "low-cost coréenne"),
    "aero k": BagRule(0, 35, "low-cost coréenne"),
    "korean air": BagRule(1, 60, "Korean Air : 1×23 kg"),
    "asiana": BagRule(1, 60, "Asiana : 1×23 kg"),
    "japan airlines": BagRule(2, 0, "JAL : 2×23 kg"),
    "ana": BagRule(2, 0, "ANA : 2×23 kg"),
    "air premia": BagRule(1, 50, "Air Premia : 1×23 kg"),
}
DEFAULT_LONG = BagRule(0, 90, "compagnie inconnue : on suppose aucune valise incluse")
DEFAULT_SHORT = BagRule(0, 40, "compagnie inconnue : on suppose aucune valise incluse")


def rule_for(airlines: list[str], duration_min: int) -> BagRule:
    long_haul = duration_min >= 6 * 60
    table = LONG_HAUL if long_haul else SHORT_HAUL
    for name in airlines:  # la 1re compagnie reconnue (transporteur principal)
        n = name.lower()
        for prefix, rule in table.items():
            if n.startswith(prefix):
                return rule
    return DEFAULT_LONG if long_haul else DEFAULT_SHORT


def bag_cost(airlines: list[str], duration_min: int, bags_per_direction: list[int]) -> tuple[int, str]:
    """Supplément valises pour un vol (1 sens = [n], A/R = [n_aller, n_retour])."""
    rule = rule_for(airlines, duration_min)
    extra = sum(max(0, n - rule.included) for n in bags_per_direction) * rule.fee
    return extra, rule.note
