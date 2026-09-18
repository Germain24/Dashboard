"""Rabais étudiant Super C : 10 % du lundi au mercredi (décision user 2026-08-11).

Le rabais est accordé en caisse sur le TOTAL, promotions et circulaire comprises
(choix user) : on l'applique donc uniformément à chaque prix, sans exclure les
articles déjà soldés.

Portée réelle de ce module, à ne pas se raconter d'histoires : un facteur
uniforme sur *tous* les prix ne change aucun arbitrage. Le ratio couverture/coût
de l'optimiseur est simplement divisé par 0,9 pour tous les candidats à la fois,
donc l'argmax est identique ; de même, dans `sante/preparations.py`, ingrédients
et équivalent commercial baissent d'autant, et les verdicts cuisiner/acheter
restent inchangés. Ce qui change est le coût PRÉVU (facture affichée, budget) —
c'est de la justesse comptable, pas une meilleure optimisation.

Le jour de référence est le jour d'ACHAT de la fenêtre
(`sante.fenetre.shopping_day_for`), jamais « aujourd'hui » : on chiffre un
panier qui sera payé le lundi ou le mercredi, même si on le calcule un autre
jour (régénération manuelle, rattrapage du planificateur).
"""
from __future__ import annotations

import datetime as dt
import os

#: Taux du rabais étudiant (0.10 = 10 %).
STUDENT_DISCOUNT_RATE = 0.10

#: Jours d'ouverture du rabais — Python weekday() : lundi=0 … dimanche=6.
STUDENT_DISCOUNT_WEEKDAYS = frozenset({0, 1, 2})


def is_enabled() -> bool:
    """Désactivable par `STUDENT_DISCOUNT=0` (le user peut perdre son statut
    étudiant, ou vouloir chiffrer un panier au prix plein)."""
    return os.getenv("STUDENT_DISCOUNT", "1") in ("1", "true", "True")


def applies_on(day: dt.date | None) -> bool:
    """Le rabais s'applique-t-il pour un achat effectué le `day` ?

    `day=None` (appelant sans contexte de fenêtre) -> False : on ne suppose
    jamais un rabais qu'on n'a pas de quoi justifier, pour ne pas SOUS-estimer
    la facture.
    """
    if day is None or not is_enabled():
        return False
    return day.weekday() in STUDENT_DISCOUNT_WEEKDAYS


def factor(day: dt.date | None) -> float:
    """Multiplicateur à appliquer aux prix pour un achat le `day` (1.0 ou 0.9)."""
    return 1.0 - STUDENT_DISCOUNT_RATE if applies_on(day) else 1.0


def apply(price: float, day: dt.date | None) -> float:
    """Prix remisé pour un achat le `day`. Les valeurs non numériques ou
    négatives sont rendues telles quelles (contrat best-effort du pipeline prix)."""
    try:
        value = float(price)
    except (TypeError, ValueError):
        return price
    if value <= 0.0:
        return price
    return value * factor(day)
