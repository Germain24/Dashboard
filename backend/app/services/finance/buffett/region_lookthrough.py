"""Agrégation déterministe des expositions pays en grandes régions économiques."""

from __future__ import annotations

import unicodedata

from .country_normalization import canonical_country


def _key(value: str) -> str:
    return unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().strip().lower()


_NORTH_AMERICA = {"united states", "etats-unis", "usa", "canada"}
_EUROPE = {
    "france", "germany", "allemagne", "italy", "italie", "spain", "espagne",
    "greece", "grece", "portugal", "netherlands", "pays-bas", "belgium", "belgique",
    "austria", "autriche", "switzerland", "suisse", "united kingdom", "royaume-uni",
    "ireland", "irlande", "sweden", "suede", "denmark", "danemark", "finland",
    "finlande", "norway", "norvege", "poland", "pologne",
}
_DEVELOPED_ASIA = {
    "japan", "japon", "australia", "australie", "new zealand", "nouvelle-zelande",
    "singapore", "hong kong",
}
_EMERGING_ASIA = {
    "china", "chine", "india", "inde", "taiwan", "south korea", "coree du sud",
    "indonesia", "indonesie", "malaysia", "malaisie", "thailand", "thailande",
    "philippines", "vietnam",
}
_LATIN_AMERICA = {
    "brazil", "bresil", "mexico", "mexique", "chile", "chili", "peru", "perou",
    "colombia", "colombie", "argentina", "argentine",
}
_EMEA = {
    "saudi arabia", "arabie saoudite", "south africa", "afrique du sud", "israel",
    "turkey", "turquie", "united arab emirates", "emirats arabes unis", "qatar",
}


def country_region(country: str) -> str:
    key = _key(canonical_country(country))
    if key in _NORTH_AMERICA:
        return "Amerique du Nord"
    if key in _EUROPE:
        return "Europe"
    if key in _DEVELOPED_ASIA:
        return "Asie developpee"
    if key in _EMERGING_ASIA:
        return "Asie emergente"
    if key in _LATIN_AMERICA:
        return "Amerique latine"
    if key in _EMEA:
        return "Moyen-Orient et Afrique"
    return "Inconnu"


def aggregate_regions(exposures: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for ticker, countries in exposures.items():
        regions: dict[str, float] = {}
        for country, weight in countries.items():
            region = country_region(country)
            regions[region] = regions.get(region, 0.0) + max(float(weight), 0.0)
        result[str(ticker).upper()] = regions
    return result
