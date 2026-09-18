"""Seed Germain — port des 4 programmes Garmin (Push / Pull / Legs / Upper).

Idempotent : ré-appel n'écrase pas les slots si déjà peuplés.
Lower (samedi) reste vide tant que Germain ne l'a pas défini dans Garmin.

Source des données : exports texte de l'app Garmin Connect partagés par
Germain le 2026-05-18.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.entrainement import Exercice, ProgrammeJour
from app.services.entrainement.exercises import create_exercice
from app.services.entrainement.programs import (
    ensure_active_program,
    get_program_day,
    update_program_day,
)

# ─────────────────────────────────────────────────────────────────────────────
# Exos manquants au seed maison (avec source="garmin").
# Format : (nom, categorie, muscles, type_mouvement, unilateral, note)
# ─────────────────────────────────────────────────────────────────────────────

GARMIN_EXERCICES: list[tuple] = [
    # Push spécifiques Garmin
    ("Incline Barbell Bench Press", "push", ["pectoraux", "triceps", "epaules"], "compose", False, "Banc incliné 30-45°"),
    ("Dumbbell Shoulder Press", "push", ["epaules", "triceps"], "compose", True, "Assis ou debout"),
    ("Dumbbell Lying Triceps Extension", "push", ["triceps"], "isolation", True, "Skullcrusher"),
    ("Incline Reverse Fly", "push", ["epaules", "trapezes"], "isolation", True, "Bent-over cable flye, deltoides postérieurs"),
    ("Lateral Raise", "push", ["epaules"], "isolation", True, None),
    ("Banded Lateral Raise", "push", ["epaules"], "isolation", True, "Élastique ou câble"),
    ("Weight-plate Front Raise", "push", ["epaules"], "isolation", False, "Disque tenu à deux mains"),
    ("Diamond Push-up", "push", ["triceps", "pectoraux"], "compose", False, "Mains rapprochées"),
    ("Cable Overhead Triceps Extension", "push", ["triceps"], "isolation", False, "Bras au-dessus de la tête"),
    # Pull spécifiques Garmin
    ("Kneeling Lat Pull-down", "pull", ["dorsaux", "biceps"], "compose", False, "À genoux devant la poulie haute"),
    ("Dumbbell Row", "pull", ["dorsaux", "biceps", "trapezes"], "compose", True, "Buste penché ou banc"),
    ("Behind-the-Back Smith Machine Shrug", "pull", ["trapezes"], "isolation", False, "Smith machine, barre derrière le dos"),
    ("Banded Fly", "pull", ["epaules", "trapezes"], "isolation", True, "Reverse fly aux élastiques — deltoides postérieurs"),
    ("Cable Biceps Curl", "pull", ["biceps"], "isolation", False, "Poulie basse"),
    ("Seated Cable Row", "pull", ["dorsaux", "biceps", "trapezes"], "compose", False, "Assis poulie basse"),
    ("Cable Fly", "push", ["pectoraux"], "isolation", True, "Poulies, mouvement de cross-over"),
    # Legs spécifiques Garmin
    ("Leg Press", "legs", ["quadriceps", "fessiers"], "compose", False, None),
    ("Leg Extensions", "legs", ["quadriceps"], "isolation", False, None),
    ("GHD Back Extensions", "legs", ["fessiers", "ischios", "lombaires"], "compose", False, "Glute Ham Raise / banc romain"),
    ("Seated Calf Raise", "legs", ["mollets"], "isolation", False, "Banc assis"),
    ("Hanging Leg Raise", "core", ["abdominaux"], "isolation", False, "Suspension à la barre"),
    # Cardio / warmup
    ("Jump Rope", "cardio", ["mollets", "cardio"], "compose", False, "Corde à sauter — warmup ~5 min"),
    ("Treadmill", "cardio", ["cardio"], "compose", False, "Tapis — warmup ~5 min"),
]


def seed_garmin_exercices(session: Session) -> int:
    """Insère les exos Garmin manquants. Retourne le nombre créé.

    Idempotent + robuste aux race conditions : `create_exercice` attrape
    déjà `IntegrityError` et retourne l'enregistrement existant si un autre
    thread l'a créé entre-temps. On ne compte que les insertions où l'id
    est nouveau (created_at récent).
    """
    existing = set(session.exec(select(Exercice.nom)).all())
    created = 0
    for nom, cat, muscles, tm, uni, note in GARMIN_EXERCICES:
        if nom in existing:
            continue
        try:
            create_exercice(
                session, nom=nom, categorie=cat, muscles=list(muscles),
                type_mouvement=tm, unilateral=uni, source="garmin", note=note,
            )
            created += 1
        except IntegrityError:
            # Filet de sécurité supplémentaire si create_exercice échoue malgré
            # tout (cas extrême sur sqlite avec WAL désactivé).
            session.rollback()
    return created


# ─────────────────────────────────────────────────────────────────────────────
# Programmes hebdomadaires (slots des ProgrammeJour).
# Format slot : {"label": str, "sets_target": int, "reps_target": int|str,
#                "note": str|None}
# ─────────────────────────────────────────────────────────────────────────────

# Lundi (Push) — programme Garmin "Push" tel que dumpé par Germain
PUSH_SLOTS: list[dict] = [
    {"label": "Treadmill (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": "Échauffement cardio"},
    {"label": "Jump Rope (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": "Optionnel"},
    {"label": "Incline Barbell Bench Press", "sets_target": 3, "reps_target": "8/5/15", "note": "Pyramidal descendant"},
    {"label": "Dumbbell Shoulder Press", "sets_target": 3, "reps_target": 12, "note": None},
    {"label": "Dumbbell Lying Triceps Extension", "sets_target": 3, "reps_target": 8, "note": "Skullcrusher"},
    {"label": "Incline Reverse Fly", "sets_target": 3, "reps_target": 12, "note": "Bent-over cable flye"},
    {"label": "Lateral Raise", "sets_target": 3, "reps_target": 20, "note": None},
    {"label": "Weight-plate Front Raise", "sets_target": 2, "reps_target": 20, "note": None},
    {"label": "Diamond Push-up", "sets_target": 1, "reps_target": 10, "note": "Finisher"},
]

# Mardi (Pull) — programme Garmin "Pull"
PULL_SLOTS: list[dict] = [
    {"label": "Jump Rope (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": None},
    {"label": "Treadmill (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": None},
    {"label": "Kneeling Lat Pull-down", "sets_target": 3, "reps_target": 15, "note": "À genoux"},
    {"label": "Pull-up", "sets_target": 1, "reps_target": "3 min", "note": "AMRAP poids du corps"},
    {"label": "Dumbbell Row", "sets_target": 3, "reps_target": 13, "note": "Unilatéral"},
    {"label": "Behind-the-Back Smith Machine Shrug", "sets_target": 3, "reps_target": 12, "note": None},
    {"label": "Banded Fly", "sets_target": 3, "reps_target": 12, "note": "Reverse fly, deltoides post."},
    {"label": "Cable Biceps Curl", "sets_target": 3, "reps_target": 12, "note": None},
]

# Mercredi (Legs) — programme Garmin "Leg"
LEGS_SLOTS: list[dict] = [
    {"label": "Jump Rope (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": None},
    {"label": "Treadmill (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": None},
    {"label": "Soulevé de terre", "sets_target": 5, "reps_target": "8/4/2/1/5", "note": "Pyramide descendante + back-off"},
    {"label": "Soulevé de terre roumain", "sets_target": 3, "reps_target": 8, "note": "Jambes tendues (RDL)"},
    {"label": "Leg Press", "sets_target": 4, "reps_target": 12, "note": None},
    {"label": "GHD Back Extensions", "sets_target": 3, "reps_target": 10, "note": "Glute Ham Raise"},
    {"label": "Leg Extensions", "sets_target": 3, "reps_target": 10, "note": None},
    {"label": "Seated Calf Raise", "sets_target": 4, "reps_target": 20, "note": None},
    {"label": "Hanging Leg Raise", "sets_target": 3, "reps_target": 20, "note": "Abdos"},
]

# Vendredi (Upper) — programme Garmin "Upper"
UPPER_SLOTS: list[dict] = [
    {"label": "Treadmill (warm-up)", "sets_target": 1, "reps_target": "5 min", "note": None},
    {"label": "Incline Barbell Bench Press", "sets_target": 3, "reps_target": 8, "note": None},
    {"label": "Seated Cable Row", "sets_target": 2, "reps_target": 12, "note": "Avec cable fly"},
    {"label": "Pull-up", "sets_target": 3, "reps_target": 8, "note": "Poids du corps"},
    {"label": "Banded Lateral Raise", "sets_target": 2, "reps_target": 10, "note": "Câble"},
    {"label": "Bent-over Row with Barbell", "sets_target": 2, "reps_target": 8, "note": None},
    {"label": "Cable Overhead Triceps Extension", "sets_target": 2, "reps_target": 10, "note": None},
]

# Mapping weekday → (label_jour, slots).
# Décision Germain (2026-05-18) : Lower (samedi = 5) reproduit Legs.
# On garde le label "Lower" pour la lisibilité du split PPL/UL, mais
# les slots sont identiques à mercredi.
GARMIN_WEEKDAYS: dict[int, tuple[str, list[dict]]] = {
    0: ("Push", PUSH_SLOTS),
    1: ("Pull", PULL_SLOTS),
    2: ("Legs", LEGS_SLOTS),
    4: ("Upper", UPPER_SLOTS),
    5: ("Lower", LEGS_SLOTS),
}


def seed_garmin_programs(session: Session, *, force: bool = False) -> dict:
    """Peuple les ProgrammeJour.slots du programme actif.

    Idempotent : si `force=False`, n'écrase un jour que si ses slots sont vides.
    Avec `force=True`, écrase tous les jours configurés (utile après un import
    Garmin mis à jour).

    Retourne un récap : {"exos_crees": N, "jours_seedes": [labels], "jours_skipped": [...]}.
    """
    prog = ensure_active_program(session)
    exos_crees = seed_garmin_exercices(session)
    jours_seedes: list[str] = []
    jours_skipped: list[str] = []
    for weekday, (label, slots) in GARMIN_WEEKDAYS.items():
        pj = get_program_day(session, prog.id, weekday)
        if pj is None:
            continue
        if pj.slots and not force:
            jours_skipped.append(label)
            continue
        update_program_day(session, prog.id, weekday, label=label, slots=slots)
        jours_seedes.append(label)
    return {
        "exos_crees": exos_crees,
        "jours_seedes": jours_seedes,
        "jours_skipped": jours_skipped,
        "lower_a_definir": False,  # depuis 2026-05-18 : Lower = Legs (décision Germain)
    }
