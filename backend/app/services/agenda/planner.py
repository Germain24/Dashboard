"""Planificateur d'agenda automatique (placeur glouton à règles).

Voir docs/superpowers/specs/2026-06-04-agenda-auto-planner-design.md

Cœur **pur** (pas de session DB) : `plan_cycle` prend la date de lancement et la
liste des blocs fixes (travail/cours) + les cours du cycle, et renvoie une
proposition de blocs déplaçables placés autour des fixes. Testable sans stack web.

Priorité (du plus protégé au premier sacrifié) :
    Travail/cours (fixes) > Sommeil > Batch cooking > Sport > Révisions
Un bloc qui ne rentre pas n'est jamais rogné : il est signalé dans `non_places`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.services.agenda.slots import free_slots

# ── Constantes de règles ────────────────────────────────────────────────────
# Python weekday() : lundi=0 … dimanche=6
# Lundi et mercredi : les courses et la cuisine suivent le rabais étudiant
# Super C (lun→mer). Le mercredi couvre jeu-dim, le lundi couvre lun-mer —
# cf. `sante.fenetre.shopping_day_for`, qui doit rester cohérent avec ceci.
COOKING_WEEKDAYS = {0, 2}          # lundi, mercredi
SPORT_SPLIT_BY_WEEKDAY = {0: "Push", 1: "Pull", 2: "Legs", 4: "Upper", 5: "Lower"}
SPORT_WEEKDAYS = set(SPORT_SPLIT_BY_WEEKDAY)  # lun, mar, mer, ven, sam

SLEEP_START_H = 23
SLEEP_DURATION_MIN = 9 * 60
SLEEP_WINDOW_START_H = 20
SLEEP_WINDOW_END_H = 12
SLEEP_WAKE_BUFFER_MIN = 45
DAY_START_H = 7                    # bornes de la journée « active » (hors sommeil)
DAY_END_H = 23

CUISINE_PREF_H = 16
CUISINE_DURATION_MIN = 120

SPORT_DURATION_MIN = 90
SPORT_PREF_TIMES = [(7, 30), (12, 30), (18, 0)]   # matin de préférence, sinon midi/soir

REVISION_DURATION_MIN = 120

BUFFER_MIN = 15

# Préférences de moment (page Préférences) → heures d'essai par activité.
MOMENT_TIMES: dict[str, list[tuple[int, int]]] = {
    "matin": [(7, 30), (9, 0), (10, 30)],
    "aprem": [(12, 30), (14, 0), (16, 0)],
    "soir": [(18, 0), (19, 30), (20, 30)],
}


def _moment_times(moment: str | None) -> list[tuple[int, int]] | None:
    """Heures d'essai pour un moment préféré ('matin'|'aprem'|'soir'), sinon None."""
    return MOMENT_TIMES.get(moment) if moment else None


# Métadonnées par type de bloc (pour l'écriture en événements côté commit).
TYPE_META: dict[str, dict[str, str]] = {
    "sommeil": {"categorie": "autre", "couleur": "#6366F1"},
    "cuisine": {"categorie": "autre", "couleur": "#16A34A"},
    "revision": {"categorie": "cours", "couleur": "#2563EB"},
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

    Cuisine lundi/mercredi : lundi -> (mardi, mercredi) ;
    mercredi -> (jeudi, lundi suivant) ; dimanche -> (lundi, lundi).
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
    if pref_times:
        preferences = [dt.datetime.combine(date, dt.time(ph, pm)) for ph, pm in pref_times]
        best = min(
            slots,
            key=lambda s: min(abs((s["debut"] - pref).total_seconds()) for pref in preferences),
        )
        return best["debut"], best["debut"] + dur
    first = slots[0]["debut"]
    return first, first + dur


def _find_sleep_slot(
    date: dt.date,
    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]],
    preferred_start: dt.datetime | None = None,
) -> tuple[dt.datetime, dt.datetime] | None:
    """Place 9 h de sommeil entre 20 h et 12 h, avant les obligations fixes.

    On préfère commencer à 23 h, puis on choisit le créneau disponible le plus
    proche de cette heure. Une marge de 45 min est réservée avant chaque
    événement suivant le sommeil. Les événements du jour suivant sont aussi
    pris en compte car la nuit traverse minuit.
    """
    start = dt.datetime.combine(date, dt.time(SLEEP_WINDOW_START_H))
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(SLEEP_WINDOW_END_H))
    duration = dt.timedelta(minutes=SLEEP_DURATION_MIN)
    wake_buffer = dt.timedelta(minutes=SLEEP_WAKE_BUFFER_MIN)
    occupied = sorted(
        (max(a - wake_buffer, start), min(b, end))
        for day in (date, date + dt.timedelta(days=1))
        for a, b in fixed_by_day.get(day, [])
        if a - wake_buffer < end and b > start
    )
    gaps: list[tuple[dt.datetime, dt.datetime]] = []
    cursor = start
    for a, b in occupied:
        if a > cursor:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append((cursor, end))

    preferred = preferred_start or dt.datetime.combine(date, dt.time(SLEEP_START_H))
    candidates = [
        (max(gap_start, min(preferred, gap_end - duration)),
         max(gap_start, min(preferred, gap_end - duration)) + duration)
        for gap_start, gap_end in gaps
        if gap_end - gap_start >= duration
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda slot: abs((slot[0] - preferred).total_seconds()))


def plan_cycle(
    run_date: dt.date,
    fixed_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]],
    courses_in_window: list[str],
    *,
    sport_weekdays: set[int] | None = None,
    moments: dict[str, str] | None = None,
    revisions_by_day: dict[dt.date, list[tuple[dt.datetime, dt.datetime]]] | None = None,
) -> Proposal:
    """Place les blocs déplaçables autour des fixes. Fonction pure.

    `fixed_by_day` : pour chaque jour, les intervalles occupés par les fixes
    (travail, cours). `courses_in_window` : cours distincts → 2h de révision chacun.
    `sport_weekdays` : jours de sport (depuis le programme d'entraînement actif) ;
    défaut `SPORT_WEEKDAYS`. `moments` : moment préféré par activité (page
    Préférences), ex. {"sport": "matin", "etudes": "soir", "cuisine": "aprem"}.
    """
    sport_days = SPORT_WEEKDAYS if sport_weekdays is None else sport_weekdays
    moments = moments or {}
    revisions_by_day = revisions_by_day or {}
    sport_pref = _moment_times(moments.get("sport")) or SPORT_PREF_TIMES
    cuisine_pref = _moment_times(moments.get("cuisine")) or [(CUISINE_PREF_H, 0)]
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

    # 1. Santé — sommeil : 9 h dans la fenêtre 20 h–12 h, autour des fixes.
    # Le sommeil est prioritaire sur les révisions planifiées : elles seront
    # déplacées/replanifiées autour du sommeil par leur propre planificateur.
    sleep_fixed = {
        d: [event for event in events if event not in revisions_by_day.get(d, [])]
        for d, events in fixed_by_day.items()
    }
    for d in days:
        preferred_sleep = None
        if d.weekday() in sport_days and (moments.get("sport") == "soir"):
            # Un coucher plus tôt préserve la séance du soir sans rogner les 9 h.
            preferred_sleep = dt.datetime.combine(d, dt.time(SLEEP_WINDOW_START_H))
        slot = _find_sleep_slot(d, sleep_fixed, preferred_sleep)
        if slot:
            prop.blocks.append(Block(d, slot[0], slot[1], "sommeil", "Sommeil"))
            # Les activités flexibles sont placées avec une marge générique
            # de 15 min. Ajouter 30 min ici réserve donc 45 min après le réveil.
            guarded_slot = (slot[0], slot[1] + dt.timedelta(minutes=SLEEP_WAKE_BUFFER_MIN - BUFFER_MIN))
            occ.setdefault(slot[0].date(), []).append(guarded_slot)
            occ.setdefault(slot[1].date(), []).append(guarded_slot)
        else:
            prop.non_places.append(f"Sommeil ({d:%a %d/%m}) : pas de créneau de 9 h entre 20 h et 12 h")

    # 2. Courses + batch cooking — 2h le jour de cuisine de la fenêtre.
    cook_day = end if end.weekday() in COOKING_WEEKDAYS else None
    if cook_day is not None:
        slot = _find_slot(cook_day, occ[cook_day], CUISINE_DURATION_MIN, cuisine_pref)
        if slot:
            add(cook_day, slot[0], slot[1], "cuisine", "Courses + batch cooking")
        else:
            prop.non_places.append(f"Cuisine ({cook_day:%a %d/%m}) : pas de créneau")

    # 3. Musculation — split hebdomadaire personnalisé, 1h30 par séance.
    for d in days:
        if d.weekday() not in sport_days:
            continue
        slot = _find_slot(d, occ[d], SPORT_DURATION_MIN, sport_pref)
        if slot:
            split = SPORT_SPLIT_BY_WEEKDAY.get(d.weekday(), "Musculation")
            add(d, slot[0], slot[1], "sport", f"Muscu — {split}")
        else:
            split = SPORT_SPLIT_BY_WEEKDAY.get(d.weekday(), "Musculation")
            prop.non_places.append(f"Muscu {split} ({d:%a %d/%m}) : pas de créneau")

    # 4. Révisions : elles sont flexibles et passent après le travail/cours,
    # le sommeil, les courses/cuisine et le sport. Toujours rattachées à un cours.
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

    prop.blocks.sort(key=lambda b: b.debut)
    return prop
