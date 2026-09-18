"""Canonicalisation unique des pays utilisés par le look-through financier."""

from __future__ import annotations

import unicodedata


def _key(value: object) -> str:
    return " ".join(
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore").decode()
        .replace("_", " ").replace("-", " ").strip().casefold().split()
    )


_GROUPS = {
    "United States": ("us", "usa", "united states", "united states of america", "etats unis"),
    "Germany": ("de", "deu", "germany", "allemagne", "deutschland"),
    "United Kingdom": ("gb", "gbr", "uk", "united kingdom", "royaume uni", "great britain"),
    "France": ("fr", "fra", "france"), "Austria": ("at", "aut", "austria", "autriche"),
    "Netherlands": ("nl", "nld", "netherlands", "pays bas"),
    "Italy": ("it", "ita", "italy", "italie"), "Spain": ("es", "esp", "spain", "espagne"),
    "Canada": ("ca", "can", "canada"), "Japan": ("jp", "jpn", "japan", "japon"),
    "Ireland": ("ie", "irl", "ireland", "irlande"),
    "Australia": ("au", "aus", "australia", "australie"),
    "Switzerland": ("ch", "che", "switzerland", "suisse"),
    "Portugal": ("pt", "prt", "portugal"), "Sweden": ("se", "swe", "sweden", "suede"),
    "Finland": ("fi", "fin", "finland", "finlande"), "Luxembourg": ("lu", "lux", "luxembourg"),
    "Denmark": ("dk", "dnk", "denmark", "danemark"), "Belgium": ("be", "bel", "belgium", "belgique"),
    "Turkey": ("tr", "tur", "turkey", "turquie", "turkiye"),
    "Mexico": ("mx", "mex", "mexico", "mexique"), "Singapore": ("sg", "sgp", "singapore", "singapour"),
    "China": ("cn", "chn", "china", "chine"), "Hong Kong": ("hk", "hkg", "hong kong"),
    "South Africa": ("za", "zaf", "south africa", "afrique du sud"),
    "Norway": ("no", "nor", "norway", "norvege"), "Peru": ("pe", "per", "peru", "perou"),
    "Israel": ("il", "isr", "israel"), "Indonesia": ("id", "idn", "indonesia", "indonesie"),
    "South Korea": ("kr", "kor", "south korea", "korea republic of", "coree du sud"),
    "Taiwan": ("tw", "twn", "taiwan"), "India": ("in", "ind", "india", "inde"),
    "Brazil": ("br", "bra", "brazil", "bresil"), "Poland": ("pl", "pol", "poland", "pologne"),
    "New Zealand": ("nz", "nzl", "new zealand", "nouvelle zelande"),
}
_LOOKUP = {alias: name for name, aliases in _GROUPS.items() for alias in aliases}


def canonical_country(value: object, *, unknown: str = "Inconnu") -> str:
    key = _key(value)
    if not key or key in {"unknown", "inconnu", "n a", "na", "none"}:
        return unknown
    return _LOOKUP.get(key, str(value).strip())


def canonicalize_exposure(countries: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for country, weight in countries.items():
        name = canonical_country(country)
        result[name] = result.get(name, 0.0) + max(float(weight), 0.0)
    return result
