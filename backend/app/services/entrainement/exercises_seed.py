"""Seed du catalogue d'exercices — CONV 7.

Décision : seed maison de ~35 exos clés (push/pull/legs/upper/lower/core +
quelques cardio). Ajout à la volée via POST /entrainement/exercises pour
le reste. L'utilisateur pourra plus tard importer ses exercices depuis
l'app Garmin (source = "garmin") sans casser ce catalogue (`nom` est
unique → l'upsert se base dessus).
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.entrainement import Exercice


# (nom, categorie, muscles, type_mouvement, unilateral, note)
SEED_EXERCICES: list[tuple] = [
    # ── Push ──
    ("Développé couché barre", "push", ["pectoraux", "triceps", "epaules"], "compose", False, None),
    ("Développé couché haltères", "push", ["pectoraux", "triceps", "epaules"], "compose", True, None),
    ("Développé incliné haltères", "push", ["pectoraux", "epaules", "triceps"], "compose", True, "Banc 30-45°"),
    ("Développé militaire barre", "push", ["epaules", "triceps"], "compose", False, "Overhead press"),
    ("Élévations latérales", "push", ["epaules"], "isolation", True, None),
    ("Dips lestés", "push", ["pectoraux", "triceps"], "compose", False, "Poids à la ceinture"),
    ("Extension triceps poulie", "push", ["triceps"], "isolation", False, None),
    ("Pompes", "push", ["pectoraux", "triceps", "epaules"], "compose", False, None),
    # ── Pull ──
    ("Tractions pronation", "pull", ["dorsaux", "biceps"], "compose", False, "Lestées si possible"),
    ("Rowing barre", "pull", ["dorsaux", "biceps", "trapezes"], "compose", False, "Buste 45°"),
    ("Rowing haltère 1 bras", "pull", ["dorsaux", "biceps"], "compose", True, None),
    ("Tirage poulie haute", "pull", ["dorsaux", "biceps"], "compose", False, "Lat pulldown"),
    ("Curl barre", "pull", ["biceps"], "isolation", False, None),
    ("Curl haltères", "pull", ["biceps"], "isolation", True, None),
    ("Face pull", "pull", ["epaules", "trapezes"], "isolation", False, "Rotateurs"),
    ("Shrugs", "pull", ["trapezes"], "isolation", False, None),
    # ── Legs ──
    ("Squat barre", "legs", ["quadriceps", "fessiers", "ischios"], "compose", False, "Back squat"),
    ("Soulevé de terre", "legs", ["ischios", "fessiers", "dorsaux"], "compose", False, "Deadlift conventionnel"),
    ("Soulevé de terre roumain", "legs", ["ischios", "fessiers"], "compose", False, "RDL"),
    ("Presse à cuisses", "legs", ["quadriceps", "fessiers"], "compose", False, None),
    ("Fentes haltères", "legs", ["quadriceps", "fessiers"], "compose", True, None),
    ("Leg curl couché", "legs", ["ischios"], "isolation", False, None),
    ("Leg extension", "legs", ["quadriceps"], "isolation", False, None),
    ("Mollets debout", "legs", ["mollets"], "isolation", False, None),
    ("Hip thrust", "legs", ["fessiers", "ischios"], "compose", False, None),
    # ── Core ──
    ("Gainage planche", "core", ["abdominaux"], "isolation", False, "Plank statique"),
    ("Crunchs", "core", ["abdominaux"], "isolation", False, None),
    ("Relevés de jambes suspendu", "core", ["abdominaux"], "isolation", False, None),
    ("Rotations russes", "core", ["abdominaux", "obliques"], "isolation", False, None),
    # ── Upper / Lower (composites — utilisés dans les jours UL) ──
    ("Pull-ups (poids du corps)", "upper", ["dorsaux", "biceps"], "compose", False, "Souvent inclus en Upper"),
    ("Goblet squat", "lower", ["quadriceps", "fessiers"], "compose", False, None),
    # ── Cardio ──
    ("Course à pied", "cardio", ["cardio"], "compose", False, "Distance + temps"),
    ("Marche rapide", "cardio", ["cardio"], "compose", False, "Récupération active"),
]


def seed_exercices(session: Session) -> int:
    """Insère les exercices manquants. Retourne le nombre créé."""
    existing = {e.nom for e in session.exec(select(Exercice.nom)).all()}
    created = 0
    for nom, categorie, muscles, type_mvt, uni, note in SEED_EXERCICES:
        if nom in existing:
            continue
        e = Exercice(
            nom=nom,
            categorie=categorie,
            muscles=list(muscles),
            type_mouvement=type_mvt,
            unilateral=uni,
            source="seed",
            note=note,
        )
        session.add(e)
        created += 1
    if created:
        session.commit()
    return created
