"""Redirections CIQUAL vérifiées pour des libellés commerciaux ambigus.

Le rapprochement lexical ne peut pas deviner que « pâtes aux œufs » désigne
des pâtes alimentaires plutôt qu'une pâte sucrée, ni que « à l'érable » décrit
une marinade et non l'aliment principal. Ces règles étroites corrigent ces cas
sans généraliser abusivement à tout le catalogue.
"""
from __future__ import annotations

import unicodedata


def _normalized(value: str) -> str:
    value = str(value).lower().replace("œ", "oe").replace("æ", "ae")
    return "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def ciqual_override_code(product_name: str) -> str | None:
    """Code CIQUAL vérifié pour un produit connu, sinon ``None``."""
    name = _normalized(product_name)

    if any(brand in name for brand in ("gatorade", "powerade")) or "boisson pour sportif" in name:
        return "18350"  # Boisson diététique pour le sport

    if "croustille" in name and not any(word in name for word in ("mais", "tortilla", "crevette")):
        return "4004"  # Chips de pommes de terre nature ou aromatisées

    if "croissant" in name and "jambon" not in name:
        return "7615"  # Croissant ordinaire, artisanal

    if "haricot" in name and "jaune" in name:
        return "20195"  # Haricot beurre, cru

    if "luzerne" in name and any(
        marker in name for marker in ("aquafuchsia", "germee", "pousse")
    ):
        return "15029"  # Luzerne, graine germée (et non graine sèche)

    if "pates" in name and "oeufs" in name and any(
        shape in name for shape in ("fettuccine", "pappardelle", "tagliatelle")
    ):
        return "9821"  # Pâtes sèches, aux œufs, crues

    if "porc" in name and any(cut in name for cut in ("surlonge", "longe")):
        return "28003"  # Porc, longe, crue

    if "peches tranchees" in name:
        if any(container in name for container in ("jus", "sirop")):
            return "13731"  # Pêche appertisée, non égouttée
        if any(state in name for state in ("surgelee", "congelee")):
            return "13043"  # Pêche crue, approximation du fruit surgelé nature

    return None
