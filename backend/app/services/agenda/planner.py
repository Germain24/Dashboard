"""Planificateur d'agenda automatique (placeur glouton à règles).

Voir docs/superpowers/specs/2026-06-04-agenda-auto-planner-design.md

Cœur **pur** (pas de session DB) : `plan_cycle` prend la date de lancement et la
liste des blocs fixes (travail/cours) + les cours du cycle, et renvoie une
proposition de blocs déplaçables placés autour des fixes. Testable sans stack web.

Priorité (du plus protégé au premier sacrifié) :
    Santé (sommeil + repas) > Cuisine > Révision > Sport
Un bloc qui ne rentre pas n'est jamais rogné : il est signalé dans `non_places`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.services.agenda.slots import free_slots

# ── Constantes de règles ────────────────────────────────────────────────────
# Python weekday() : lundi=0 … dimanche=6
COOKING_WEEKDAYS = {3, 6}          # jeudi, dimanche
SPORT_WEEKDAYS = {0, 1, 2, 4, 5}   # lun, mar, mer, ven, sam

SLEEP_START_H = 23
SLEEP_DURATION_MIN = 8 * 60
DAY_START_H = 7                    # bornes de la journée « active » (hors sommeil)
DAY_END_H = 23

MEALS = [  # (heure, minute, titre) — ancres ± MEAL_FLEX_MIN, peuvent chevaucher le travail
    (7, 30, "Petit-déjeuner"),
    (12, 30, "Déjeuner"),
    (19, 30, "Dîner"),
]
MEAL_DURATION_MIN = 30

CUISINE_PREF_H = 16
CUISINE_DURATION_MIN = 120

SPORT_DURATION_MIN = 90
SPORT_PREF_TIMES = [(7, 30), (12, 30), (18, 0)]   # matin de préférence, sinon midi/soir

REVISION_DURATION_MIN = 120

ETUDES_SESSION_MIN = 90           # bloc d'études depuis l'objectif hebdo
ETUDES_PREF_TIMES = [(9, 0), (14, 0)]

BUFFER_MIN = 15

# Métadonnées par type de bloc (pour l'écriture en événements côté commit).
TYPE_META: dict[str, dict[str, str]] = {
    "sommeil": {"categorie": "autre", "couleur": "#6366F1"},
    "repas": {"categorie": "autre", "couleur": "#14B8A6"},
    "cuisine": {"categorie": "autre", "couleur": "#16A34A"},
    "revision": {"categorie": "cours", "couleur": "#2563EB"},
    "etudes": {"categorie": "etudes", "couleur": "#6366F1"},
    "sport": {"categorie": "sport", "couleur": "#F59E0B"},
}


@dataclass
class Block:
    date: dt.date
    debut: dt.datetime
    fin: dt.datetime
    type: str
    titre: str


@dataclass
class Proposal:
    window_start: dt.date
    window_end: dt.date
    blocks: list[Block] = field(default_factory=list)
    non_places: list[str] = field(default_factory=list)


# ── Fenêtre du cycle ─────────────────────────────────────────────────────────

def cycle_window(run_date: dt.date) -> tuple[dt.date, dt.date]:
    """Du lendemain de `run_date` jusqu'au prochain jour de cuisine inclus.

    jeudi  -> (vendredi, dimanche) ; dimanche -> (lundi, jeudi).
    """
    start = run_date + dt.timedelta(days=1)
    end = start
    while end.weekday() not in COOKING_WEEKDAYS:
        end += dt.timedelta(days=1)
    return start, end


def _window_days(start: dt.date, end: dt.date) -> list[dt.date]:
    days, d = [], start
    while d <= end:
        days.append(d)
        d += dt.timedelta(days=1)
    return days


# ── Placement ────────────────────────────────────────────────────────────────

def _inflate(
    occupied: list[tuple[dt.datetime, dt.datetime]], buffer_min: int
) -> list[tuple[dt.datetime, dt.datetime]]:
    pad = dt.timedelta(minutes=buffer_min)
    return [(s - pad, e + pad) for s, e in occupied]


def _find_slot(
    date: dt.date,
    occupied: list[tuple[dt.datetime, dt.datetime]],
    duration_min: int,
    pref_times: list[tuple[int, int]] | None = None,
) -> tuple[dt.datetime, dt.datetime] | None:
    """Trouve un créneau de `duration_min` dans la journée, tampon 15 min inclus.

    Si `pref_times` est fourni, tente de démarrer à l'une de ces heures (dans
    l'ordre) ; sinon prend le créneau libre le plus tôt.
    """
    dur = dt.timedelta(minutes=duration_min)
    slots = free_slots(
        date,
        _inflate(occupied, BUFFER_MIN),
        min_duration_min=duration_min,
        day_start_h=DAY_START_H,
        day_end_h=DAY_END_H,
    )
    if not slots:
        return None
    for ph, pm in pref_times or []:
        pref = dt.datetime.combine(date, dt.time(ph, pm))
        for s in slots:
            if s["debut"] <= pref and pref + dur <= s["fin"]:
                return pref, pref + dur
    first = slots[0]["debut"]
    return first, first + dur


def plan_cycle(
    run_date: dt.date,
    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]],
    courses_in_window: list[str],
    *,
    sport_weekdays: set[int] | None = None,
    etudes_target_min: int = 0,
) -> Proposal:
    """Place les blocs déplaçables autour des fixes. Fonction pure.

    `fixed_by_day` : pour chaque jour, les intervalles occupés par les fixes
    (travail, cours). `courses_in_window` : cours distincts → 2h de révision chacun.
    `sport_weekdays` : jours de sport (depuis le programme d'entraînement actif) ;
    défaut `SPORT_WEEKDAYS`. `etudes_target_min` : minutes d'études à placer
    (depuis l'objectif hebdo) en plus des révisions, dans les créneaux libres.
    """
    sport_days = SPORT_WEEKDAYS if sport_weekdays is None else sport_weekdays
    start, end = cycle_window(run_date)
    days = _window_days(start, end)
    prop = Proposal(window_start=start, window_end=end)

    # Occupé courant par jour (copie des fixes), enrichi au fur et à mesure.
    occ: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]] = {
        d: list(fixed_by_day.get(d, [])) for d in days
    }

    def add(d: dt.date, debut: dt.datetime, fin: dt.datetime, typ: str, titre: str) -> None:
        prop.blocks.append(Block(date=d, debut=debut, fin=fin, type=typ, titre=titre))
        occ.setdefault(d, []).append((debut, fin))

    # 1. Santé — Sommeil (nuit, hors 7-23 donc n'entre pas en concurrence).
    for d in days:
        debut = dt.datetime.combine(d, dt.time(SLEEP_START_H, 0))
        fin = debut + dt.timedelta(minutes=SLEEP_DURATION_MIN)
        prop.blocks.append(Block(d, debut, fin, "sommeil", "Sommeil"))

    # 2. Santé — Repas (ancres fixes, autorisés à chevaucher le travail).
    for d in days:
        for h, m, titre in MEALS:
            debut = dt.datetime.combine(d, dt.time(h, m))
            fin = debut + dt.timedelta(minutes=MEAL_DURATION_MIN)
            add(d, debut, fin, "repas", titre)

    # 3. Cuisine — 2h le jour de cuisine de la fenêtre (le dernier jour).
    cook_day = end if end.weekday() in COOKING_WEEKDAYS else None
    if cook_day is not None:
        slot = _find_slot(cook_day, occ[cook_day], CUISINE_DURATION_MIN, [(CUISINE_PREF_H, 0)])
        if slot:
            add(cook_day, slot[0], slot[1], "cuisine", "Batch cooking")
        else:
            prop.non_places.append(f"Cuisine ({cook_day:%a %d/%m}) : pas de créneau")

    # 4. Révision — 2h par cours distinct, n'importe quel créneau libre du cycle.
    for course in courses_in_window:
        placed = False
        for d in days:
            slot = _find_slot(d, occ[d], REVISION_DURATION_MIN)
            if slot:
                add(d, slot[0], slot[1], "revision", f"Révision — {course}")
                placed = True
                break
        if not placed:
            prop.non_places.append(f"Révision « {course} » : pas de créneau")

    # 5. Sport — 1h30 les jours de sport (programme actif), matin sinon midi/soir.
    for d in days:
        if d.weekday() not in sport_days:
            continue
        slot = _find_slot(d, occ[d], SPORT_DURATION_MIN, SPORT_PREF_TIMES)
        if slot:
            add(d, slot[0], slot[1], "sport", "Sport")
        else:
            prop.non_places.append(f"Sport ({d:%a %d/%m}) : pas de créneau")

    # 6. Études — depuis l'objectif hebdo, par blocs, dans les créneaux libres.
    placed_etudes = 0
    for d in days:
        if placed_etudes >= etudes_target_min:
            break
        dur = min(ETUDES_SESSION_MIN, etudes_target_min - placed_etudes)
        if dur < 30:
            break
        slot = _find_slot(d, occ[d], dur, ETUDES_PREF_TIMES)
        if slot:
            add(d, slot[0], slot[1], "etudes", "Études")
            placed_etudes += dur

    prop.blocks.sort(key=lambda b: b.debut)
    return prop
