"""Barème UQAM et constantes du module Études.

Décision 1.B : note brute /100 → lettre + points GPA calculés à la volée.
"""

from __future__ import annotations

# Barème UQAM A+ à E (seuils inclusifs, ordre décroissant)
# Chaque tuple : (seuil_min, lettre, points_gpa)
UQAM_BAREME: list[tuple[float, str, float]] = [
    (90.0, "A+", 4.3),
    (85.0, "A",  4.0),
    (80.0, "A-", 3.7),
    (77.0, "B+", 3.3),
    (73.0, "B",  3.0),
    (70.0, "B-", 2.7),
    (67.0, "C+", 2.3),
    (63.0, "C",  2.0),
    (60.0, "C-", 1.7),
    (57.0, "D+", 1.3),
    (54.0, "D",  1.0),
    ( 0.0, "E",  0.0),
]

TYPES_EVAL = ("exam", "devoir", "quiz", "projet", "autre")

# Priorité Agenda selon type d'évaluation (heuristique simple)
PRIORITE_PAR_TYPE: dict[str, int] = {
    "exam":    1,
    "projet":  2,
    "devoir":  3,
    "quiz":    3,
    "autre":   4,
}


def note_to_lettre(note: float) -> str:
    """Convertit une note /100 en lettre UQAM."""
    for seuil, lettre, _ in UQAM_BAREME:
        if note >= seuil:
            return lettre
    return "E"


def note_to_gpa(note: float) -> float:
    """Convertit une note /100 en points GPA /4.3."""
    for seuil, _, points in UQAM_BAREME:
        if note >= seuil:
            return points
    return 0.0
