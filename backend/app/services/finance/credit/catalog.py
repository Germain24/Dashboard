"""Catalogue des produits de crédit candidats (#marge-credit).

Valeurs = estimations heuristiques (limites de départ typiques, ancienneté
requise, seuils de pointage) — PAS une garantie d'approbation. Surchargeable
sans redéploiement via `data/imports/Finances/variables/credit_catalog.json`
(même convention que `params.json` du Buffett, cf. buffett/config.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class CreditProduct:
    institution: str
    produit: str
    type: str  # "carte_standard" | "carte_garantie" | "programme_newcomer" | "marge_personnelle"
    limite_min: float
    limite_max: float
    anciennete_min_mois: int                       # ancienneté au Canada minimale pour être éligible
    score_min_requis: int | None                    # None = pas d'exigence (newcomer / carte garantie)
    anciennete_min_avant_1ere_hausse_mois: int       # délai avant la 1ère demande de hausse
    cooldown_hausse_mois: int                        # délai entre deux hausses une fois la 1ère obtenue


DEFAULT_CATALOG: list[CreditProduct] = [
    CreditProduct("RBC", "Carte Visa Nouveaux arrivants", "programme_newcomer", 500, 3000, 0, None, 6, 12),
    CreditProduct("Scotiabank", "StartRight Visa", "programme_newcomer", 500, 5000, 0, None, 6, 12),
    CreditProduct("Home Trust", "Secured Visa", "carte_garantie", 500, 10000, 0, None, 6, 6),
    CreditProduct("Tangerine", "World Mastercard", "carte_standard", 1000, 5000, 6, 650, 12, 12),
    CreditProduct("Banque Nationale", "Marge personnelle", "marge_personnelle", 2000, 10000, 12, 680, 12, 12),
    CreditProduct("Desjardins", "Marge personnelle", "marge_personnelle", 1000, 8000, 12, 660, 12, 12),
    CreditProduct("CIBC", "Carte Visa standard", "carte_standard", 1000, 5000, 6, 640, 12, 12),
    CreditProduct("BMO", "Mastercard World Elite", "carte_standard", 3000, 15000, 18, 720, 12, 12),
]

# Règle par défaut appliquée à un compte existant qui ne correspond à aucune
# entrée du catalogue (ex. carte déjà détenue avant l'usage de cet outil).
DEFAULT_HAUSSE_RULE = CreditProduct("_defaut", "_defaut", "carte_standard", 0, 0, 0, None, 12, 12)

CATALOG_OVERRIDE_FILE: str = str(settings.imports_dir / "Finances" / "variables" / "credit_catalog.json")


def load_catalog() -> list[CreditProduct]:
    """Charge le catalogue : surcharge JSON si présente, sinon le défaut."""
    if not os.path.exists(CATALOG_OVERRIDE_FILE):
        return list(DEFAULT_CATALOG)
    try:
        with open(CATALOG_OVERRIDE_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        return [CreditProduct(**item) for item in raw]
    except Exception as e:
        print(f"[credit.catalog] Erreur chargement {CATALOG_OVERRIDE_FILE}: {e}")
        return list(DEFAULT_CATALOG)
