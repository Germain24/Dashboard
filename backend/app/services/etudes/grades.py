"""Calcul du GPA — logique pure Python, sans dépendance DB.

Décision 5.B : GPA = moyenne simple des points de tous les cours
               (chaque cours pèse identiquement).
Décision 1.B : note brute /100 → lettre + points GPA calculés à la volée.
Décision 2.B : note finale = Cours.note_finale (saisie manuelle).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.etudes.constants import note_to_gpa, note_to_lettre


@dataclass
class CoursGrade:
    cours_id: int
    code: str
    nom: str
    semestre: str
    note_finale: Optional[float]       # /100
    lettre: Optional[str]
    points_gpa: Optional[float]        # /4.3


@dataclass
class GpaResult:
    semestre: Optional[str]            # None = cumulatif
    nb_cours: int
    nb_cours_notes: int                # cours avec note_finale renseignée
    gpa: Optional[float]               # None si aucun cours noté
    detail: list[CoursGrade]


def compute_cours_grade(
    cours_id: int,
    code: str,
    nom: str,
    semestre: str,
    note_finale: Optional[float],
) -> CoursGrade:
    if note_finale is None:
        return CoursGrade(cours_id, code, nom, semestre, None, None, None)
    return CoursGrade(
        cours_id=cours_id,
        code=code,
        nom=nom,
        semestre=semestre,
        note_finale=note_finale,
        lettre=note_to_lettre(note_finale),
        points_gpa=note_to_gpa(note_finale),
    )


def compute_gpa(cours_grades: list[CoursGrade], semestre: Optional[str] = None) -> GpaResult:
    """Calcule le GPA moyen simple sur la liste de CoursGrade fournie."""
    notes = [cg.points_gpa for cg in cours_grades if cg.points_gpa is not None]
    gpa = round(sum(notes) / len(notes), 2) if notes else None
    return GpaResult(
        semestre=semestre,
        nb_cours=len(cours_grades),
        nb_cours_notes=len(notes),
        gpa=gpa,
        detail=cours_grades,
    )


def gpa_pour_semestre(
    cours_list: list[dict],        # dicts avec id/code/nom/semestre/note_finale
    semestre: str,
) -> GpaResult:
    """GPA d'un semestre précis."""
    grades = [
        compute_cours_grade(
            c["id"], c["code"], c["nom"], c["semestre"], c.get("note_finale")
        )
        for c in cours_list
        if c["semestre"] == semestre
    ]
    return compute_gpa(grades, semestre=semestre)


def gpa_cumulatif(cours_list: list[dict]) -> GpaResult:
    """GPA cumulatif sur tous les semestres."""
    grades = [
        compute_cours_grade(
            c["id"], c["code"], c["nom"], c["semestre"], c.get("note_finale")
        )
        for c in cours_list
    ]
    return compute_gpa(grades, semestre=None)
