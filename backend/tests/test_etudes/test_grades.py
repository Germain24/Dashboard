"""Tests de la logique GPA — pure Python, sans DB.

Décision 1.B : note brute → lettre + GPA calculés.
Décision 5.B : GPA = moyenne simple (tous les cours pèsent pareil).
"""

from __future__ import annotations

import pytest

from app.services.etudes.constants import note_to_gpa, note_to_lettre
from app.services.etudes.grades import (
    compute_cours_grade,
    gpa_cumulatif,
    gpa_pour_semestre,
)


# ───────────────────── Barème UQAM ───────────────────────────────

@pytest.mark.parametrize("note,expected_lettre,expected_pts", [
    (95.0, "A+", 4.3),
    (90.0, "A+", 4.3),
    (87.0, "A",  4.0),
    (85.0, "A",  4.0),
    (82.0, "A-", 3.7),
    (78.0, "B+", 3.3),
    (74.0, "B",  3.0),
    (71.0, "B-", 2.7),
    (68.0, "C+", 2.3),
    (64.0, "C",  2.0),
    (61.0, "C-", 1.7),
    (58.0, "D+", 1.3),
    (55.0, "D",  1.0),
    (54.0, "D",  1.0),
    (50.0, "E",  0.0),
    ( 0.0, "E",  0.0),
])
def test_bareme_uqam(note, expected_lettre, expected_pts):
    assert note_to_lettre(note) == expected_lettre
    assert note_to_gpa(note) == expected_pts


# ───────────────────── compute_cours_grade ───────────────────────

def test_cours_grade_with_note():
    cg = compute_cours_grade(1, "INF1000", "Intro prog", "A2026", 85.0)
    assert cg.lettre == "A"
    assert cg.points_gpa == 4.0
    assert cg.note_finale == 85.0


def test_cours_grade_without_note():
    cg = compute_cours_grade(2, "MAT2000", "Calcul", "A2026", None)
    assert cg.lettre is None
    assert cg.points_gpa is None


# ───────────────────── gpa_pour_semestre ─────────────────────────

def test_gpa_semestre_simple():
    cours = [
        {"id": 1, "code": "A", "nom": "A", "semestre": "A2026", "note_finale": 90.0},  # 4.3
        {"id": 2, "code": "B", "nom": "B", "semestre": "A2026", "note_finale": 85.0},  # 4.0
        {"id": 3, "code": "C", "nom": "C", "semestre": "H2026", "note_finale": 70.0},  # 2.7
    ]
    result = gpa_pour_semestre(cours, "A2026")
    assert result.nb_cours == 2
    assert result.nb_cours_notes == 2
    assert result.gpa == pytest.approx((4.3 + 4.0) / 2, abs=0.01)


def test_gpa_semestre_cours_non_note():
    cours = [
        {"id": 1, "code": "A", "nom": "A", "semestre": "A2026", "note_finale": 80.0},  # 3.7
        {"id": 2, "code": "B", "nom": "B", "semestre": "A2026", "note_finale": None},
    ]
    result = gpa_pour_semestre(cours, "A2026")
    assert result.nb_cours == 2
    assert result.nb_cours_notes == 1
    assert result.gpa == 3.7


def test_gpa_semestre_aucun_cours_note():
    cours = [{"id": 1, "code": "X", "nom": "X", "semestre": "A2026", "note_finale": None}]
    result = gpa_pour_semestre(cours, "A2026")
    assert result.gpa is None


def test_gpa_semestre_autre_semestre_ignore():
    cours = [
        {"id": 1, "code": "A", "nom": "A", "semestre": "H2026", "note_finale": 95.0},
        {"id": 2, "code": "B", "nom": "B", "semestre": "A2026", "note_finale": 60.0},
    ]
    result = gpa_pour_semestre(cours, "H2026")
    assert result.nb_cours == 1
    assert result.gpa == 4.3


# ───────────────────── gpa_cumulatif ─────────────────────────────

def test_gpa_cumulatif():
    cours = [
        {"id": 1, "code": "A", "nom": "A", "semestre": "A2025", "note_finale": 90.0},  # 4.3
        {"id": 2, "code": "B", "nom": "B", "semestre": "H2026", "note_finale": 73.0},  # 3.0
    ]
    result = gpa_cumulatif(cours)
    assert result.semestre is None
    assert result.nb_cours == 2
    assert result.gpa == pytest.approx((4.3 + 3.0) / 2, abs=0.01)


def test_gpa_cumulatif_liste_vide():
    result = gpa_cumulatif([])
    assert result.gpa is None
    assert result.nb_cours == 0
