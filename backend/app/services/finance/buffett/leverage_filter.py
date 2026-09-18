"""Filtre des ETF à effet de levier / inverses pour l'éligibilité à l'optimisation.

Un ETF "Daily (2x) Leveraged" ou "Daily (-1x) Inverse" se rebalance
QUOTIDIENNEMENT : sa performance cumulée diverge fortement de "N × l'indice"
sur la durée (volatility decay), même si l'indice sous-jacent est stable. Ce
sont des produits de trading tactique court terme, pas des actifs de
buy & hold — l'optimiseur STARR/Monte-Carlo peut néanmoins les choisir pour
leur faible corrélation historique avec le reste du portefeuille (bon pour le
CVaR mesuré a posteriori) sans "comprendre" que ce comportement n'est pas
fiable dans la durée. On les exclut donc en amont, avant l'optimisation.

Détection par le NOM (aucune colonne dédiée dans ToutBroker.xlsx) : on ne
matche que des signaux propres aux produits à levier, avec limites de mots
(``\\b``) pour éviter les faux positifs sur des noms contenant ces lettres par
hasard (ex. "Unilever" contient "lever", "Ultragenyx" contient "ultra",
"Short Duration High Yield" contient "short").
"""

from __future__ import annotations

import re

# "(2x)" / "(-1x)" / "(3X)" : multiplicateur entre parenthèses, spécifique aux
# produits à effet de levier/inverse (aucun faux positif connu).
_MULTIPLIER_RE = re.compile(r"\(-?\d+x\)", re.IGNORECASE)
_BARE_MULTIPLIER_RE = re.compile(r"(?<![A-Za-z0-9])-?\d+x\b", re.IGNORECASE)
# Mots entiers propres aux produits à levier/inverse. On évite volontairement
# "short" et "ultra" seuls (trop génériques : fonds obligataires "short
# duration", sociétés "Ultragenyx"...).
_WORD_RE = re.compile(r"\b(leveraged?|inverse|ultrashort|ultrapro)\b", re.IGNORECASE)
_ISSUER_SHORT_RE = re.compile(
    r"\b(?:proshares|direxion|wisdomtree|leverage\s+shares)\b.*\bshort\b|"
    r"\bshort\b.*\b(?:proshares|direxion|wisdomtree|leverage\s+shares)\b",
    re.IGNORECASE,
)
_DAILY_SHORT_RE = re.compile(r"\b(?:daily\s+short|short\s+daily)\b", re.IGNORECASE)
_BEAR_RE = re.compile(r"\b(?:daily\s+)?bear(?:\s+-?\d+x)?\b", re.IGNORECASE)


def classify_product_strategy(nom: str) -> str:
    """Classe un fonds en ``plain``, ``inverse`` ou ``leveraged``.

    ``short`` seul reste volontairement insuffisant. Les émetteurs dont la
    convention de nommage utilise explicitement ``Short`` pour les produits
    inverses sont traités séparément.
    """
    if not nom:
        return "plain"
    value = str(nom)
    if (
        _ISSUER_SHORT_RE.search(value)
        or _DAILY_SHORT_RE.search(value)
        or _BEAR_RE.search(value)
        or re.search(
        r"\b(inverse|ultrashort)\b|\(-1x\)", value, re.IGNORECASE
        )
    ):
        return "inverse"
    if _MULTIPLIER_RE.search(value) or _BARE_MULTIPLIER_RE.search(value) or re.search(
        r"\b(leveraged?|ultrapro)\b", value, re.IGNORECASE
    ):
        return "leveraged"
    return "plain"


def is_leveraged_product(nom: str) -> bool:
    """Vrai si ``nom`` désigne un ETF à effet de levier ou inverse (à exclure)."""
    return classify_product_strategy(nom) != "plain"
