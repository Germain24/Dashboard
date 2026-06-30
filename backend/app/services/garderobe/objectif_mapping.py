"""Table de correspondance déterministe sous_categorie/categorie -> type objectif.

Sert au rattachement automatique des vêtements (POST /garderobe/objectif/auto-rattacher).
Les vocabulaires ne coïncident pas (ex. « Button Up » -> « Chemises »), d'où une
table sémantique. Les pièces sans correspondance (montres, bijoux, lunettes de vue)
restent non rattachées et se gèrent au sélecteur manuel.
"""
from __future__ import annotations

import re
import unicodedata


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# Libellés lisibles -> nom EXACT d'un type objectif (cf. Vetements.xlsx).
_RAW_MAPPING: dict[str, str] = {
    "T-shirt": "T-shirts",
    "T-shirt Manches Longues": "T-shirts",
    "Polo": "Polos",
    "Chemise": "Chemises",
    "Button Up": "Chemises",
    "Chino": "Pantalons chino",
    "Jean": "Jeans",
    "Jean Ballon": "Jeans",
    "Wide-Leg": "Pantalons habillés",
    "Trackpants": "Jogging",
    "Bomber": "Vestes légères",
    "Veste Sport": "Vestes de sport",
    "Chelsea Boots": "Bottines",
    "Bottes de Neige": "Bottines",
    "Lunettes de Soleil": "Lunettes de soleil",
}

# Clés normalisées au chargement -> lookup robuste (casse/accents/séparateurs).
MAPPING: dict[str, str] = {norm(k): v for k, v in _RAW_MAPPING.items()}


def derive_type_objectif(categorie, sous_categorie, type_names) -> str | None:
    """Type objectif dérivé de la pièce, ou None si non mappable / type absent.

    Priorité à `sous_categorie`, repli sur `categorie`. Ne renvoie un type que
    s'il appartient à `type_names` (les noms d'ObjectifType courants).
    """
    names = set(type_names)
    for key in (norm(sous_categorie), norm(categorie)):
        val = MAPPING.get(key) if key else None
        if val and val in names:
            return val
    return None
