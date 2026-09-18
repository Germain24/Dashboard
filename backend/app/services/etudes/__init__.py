"""Façade publique du module Études.

Import explicite des fonctions utilisées depuis d'autres modules
(ex. routes_etudes.py).
"""

from app.services.etudes.constants import note_to_gpa, note_to_lettre
from app.services.etudes.courses import (
    create_cours,
    delete_cours,
    get_cours,
    list_cours,
    semestres_distincts,
    update_cours,
)
from app.services.etudes.evaluations import (
    create_evaluation,
    delete_evaluation,
    get_evaluation,
    list_evaluations,
    update_evaluation,
)
from app.services.etudes.grades import (
    GpaResult,
    compute_cours_grade,
    gpa_cumulatif,
    gpa_pour_semestre,
)
from app.services.etudes.sessions import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    total_minutes_par_cours,
    update_session,
)

__all__ = [
    "note_to_gpa",
    "note_to_lettre",
    "create_cours",
    "delete_cours",
    "get_cours",
    "list_cours",
    "semestres_distincts",
    "update_cours",
    "create_evaluation",
    "delete_evaluation",
    "get_evaluation",
    "list_evaluations",
    "update_evaluation",
    "GpaResult",
    "compute_cours_grade",
    "gpa_cumulatif",
    "gpa_pour_semestre",
    "create_session",
    "delete_session",
    "get_session",
    "list_sessions",
    "total_minutes_par_cours",
    "update_session",
]
