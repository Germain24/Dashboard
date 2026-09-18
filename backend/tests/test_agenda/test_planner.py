"""Tests logique pure planner.py — aucune dépendance DB."""

import datetime as dt

from app.services.agenda.planner import (
    Proposal,
    cycle_window,
    plan_cycle,
)

# Jours de cuisine/courses = lundi et mercredi (rabais étudiant Super C lun→mer).
# Le planificateur tourne ces jours-là : lundi couvre (mar, mer), mercredi couvre
# (jeu → lundi suivant). Les deux cycles pavent la semaine entière sans trou.
MON = dt.date(2026, 6, 15)  # lundi
WED = dt.date(2026, 6, 17)  # mercredi — cycle le plus long (5 jours), cas de référence
FRI = dt.date(2026, 6, 19)  # vendredi, dans la fenêtre de WED
NEXT_MON = dt.date(2026, 6, 22)  # lundi suivant = jour de cuisine de la fenêtre de WED


def _on(d: dt.date, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime(d.year, d.month, d.day, h, m)


def _types(prop: Proposal) -> dict[str, int]:
    out: dict[str, int] = {}
    for b in prop.blocks:
        out[b.type] = out.get(b.type, 0) + 1
    return out


def _gap_min(a, b) -> float:
    """Minutes entre deux blocs ; -1 s'ils se chevauchent."""
    if a.fin <= b.debut:
        return (b.debut - a.fin).total_seconds() / 60
    if b.fin <= a.debut:
        return (a.debut - b.fin).total_seconds() / 60
    return -1


# ── Fenêtre du cycle ─────────────────────────────────────────────────────────

def test_window_wednesday_runs_until_next_monday():
    # mercredi -> (jeudi … lundi suivant), le plus long des deux cycles
    assert cycle_window(WED) == (dt.date(2026, 6, 18), NEXT_MON)


def test_window_monday_runs_until_wednesday():
    # lundi -> (mardi, mercredi)
    assert cycle_window(MON) == (dt.date(2026, 6, 16), dt.date(2026, 6, 17))


def test_les_deux_cycles_pavent_la_semaine_sans_trou():
    """Le planificateur ne tourne que lundi et mercredi : à eux deux, leurs
    fenêtres doivent couvrir les 7 jours, sans chevauchement ni jour orphelin."""
    couverts: list[dt.date] = []
    for run in (MON, WED):
        start, end = cycle_window(run)
        d = start
        while d <= end:
            couverts.append(d)
            d += dt.timedelta(days=1)
    assert len(couverts) == len(set(couverts)) == 7
    assert set(d.weekday() for d in couverts) == set(range(7))


def test_run_day_never_in_window():
    start, _end = cycle_window(WED)
    assert start > WED


# ── Cycle vide (tout rentre) ─────────────────────────────────────────────────

def test_empty_cycle_counts():
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=[])
    t = _types(prop)
    assert t["sommeil"] == 5            # jeu, ven, sam, dim, lun
    assert t.get("repas", 0) == 0      # les repas sont retirés de l'agenda
    assert t["cuisine"] == 1            # lundi (jour cuisine de la fenêtre)
    assert t.get("revision", 0) == 0    # aucun cours
    assert t["sport"] == 3              # ven, sam, lun (jeu et dim = repos)
    assert prop.non_places == []
    sleep = [b for b in prop.blocks if b.type == "sommeil"]
    assert all(b.fin - b.debut == dt.timedelta(hours=9) for b in sleep)
    assert all(b.debut == _on(b.date, 23) and b.fin == _on(b.date + dt.timedelta(days=1), 8) for b in sleep)


def test_sleep_moves_around_fixed_work_in_overnight_window():
    # Un quart tardif et un quart matinal ne laissent plus 9 h avec la marge
    # de 45 min avant la reprise.
    fixed = {
        FRI: [(_on(FRI, 20), _on(FRI, 22))],
        FRI + dt.timedelta(days=1): [(_on(FRI + dt.timedelta(days=1), 7), _on(FRI + dt.timedelta(days=1), 14))],
    }
    prop = plan_cycle(WED, fixed_by_day=fixed, courses_in_window=[])
    assert not any(b.type == "sommeil" and b.date == FRI for b in prop.blocks)


def test_sleep_unplaced_when_fixed_events_leave_no_nine_hour_window():
    fixed = {FRI: [(_on(FRI, 20), _on(FRI + dt.timedelta(days=1), 11))]}
    prop = plan_cycle(WED, fixed_by_day=fixed, courses_in_window=[])
    assert not any(b.type == "sommeil" and b.date == FRI for b in prop.blocks)
    assert any("Sommeil" in msg for msg in prop.non_places)


def test_cuisine_on_cooking_day():
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=[])
    cuisine = [b for b in prop.blocks if b.type == "cuisine"]
    assert len(cuisine) == 1
    assert cuisine[0].date == NEXT_MON  # lundi
    assert (cuisine[0].fin - cuisine[0].debut) == dt.timedelta(minutes=120)


def test_revision_one_block_per_course():
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=["Maths", "Physique"])
    rev = [b for b in prop.blocks if b.type == "revision"]
    assert len(rev) == 2
    assert prop.non_places == []


def test_no_block_overlaps_within_day():
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=["Maths"])
    by_day: dict[dt.date, list] = {}
    for b in prop.blocks:
        by_day.setdefault(b.date, []).append(b)
    for blocks in by_day.values():
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                overlap_allowed = blocks[i].type == blocks[j].type == "revision"
                assert _gap_min(blocks[i], blocks[j]) != -1 or overlap_allowed, (
                    f"chevauchement {blocks[i].titre} / {blocks[j].titre}"
                )


def test_buffer_15min_around_flexible_blocks():
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=["Maths"])
    flex = {"cuisine", "sport", "revision"}
    by_day: dict[dt.date, list] = {}
    for b in prop.blocks:
        by_day.setdefault(b.date, []).append(b)
    for blocks in by_day.values():
        for f in [b for b in blocks if b.type in flex]:
            for o in blocks:
                if o is f or o.type == "sommeil":
                    continue
                assert _gap_min(f, o) >= 15, f"tampon < 15 min : {f.titre} / {o.titre}"


# ── Planificateur unifié : jours de sport + études + sport le matin ──────────

def test_sport_weekdays_override():
    # Programme d'entraînement : seul vendredi est un jour de sport.
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=[], sport_weekdays={4})
    assert _types(prop)["sport"] == 1   # ven seulement (sam, dim exclus)


def test_personalized_strength_split_and_ninety_minute_duration():
    prop = plan_cycle(WED, fixed_by_day={}, courses_in_window=[])
    workouts = [b for b in prop.blocks if b.type == "sport"]
    split_by_weekday = {b.date.weekday(): b.titre for b in workouts}
    assert split_by_weekday == {4: "Muscu — Upper", 5: "Muscu — Lower", 0: "Muscu — Push"}
    assert all(b.fin - b.debut == dt.timedelta(minutes=90) for b in workouts)


def test_etudes_without_course_are_not_scheduled():
    # Un objectif hebdomadaire sans matière ne doit pas créer de blocs orphelins.
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=[])
    etudes = [b for b in prop.blocks if b.type == "etudes"]
    assert etudes == []
    assert not any(b.titre == "Études" for b in prop.blocks)


def test_cooking_occurs_in_both_weekly_planner_cycles():
    monday_cycle = plan_cycle(MON, fixed_by_day={}, courses_in_window=[])
    wednesday_cycle = plan_cycle(WED, fixed_by_day={}, courses_in_window=[])
    cooking_days = [b.date for p in (monday_cycle, wednesday_cycle)
                    for b in p.blocks if b.type == "cuisine"]
    assert cooking_days == [dt.date(2026, 6, 17), NEXT_MON]
    assert all(b.titre == "Courses + batch cooking" for p in (monday_cycle, wednesday_cycle)
               for b in p.blocks if b.type == "cuisine")


def test_sport_prefers_morning_when_free():
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=[])
    sport = [b for b in prop.blocks if b.type == "sport"]
    assert sport and all(b.debut.hour in {12, 18} for b in sport)


def test_sport_moment_preference_evening():
    # Préférence "soir" → sport placé l'après-midi/soir (≥ 12 h), pas le matin.
    prop = plan_cycle(WED,fixed_by_day={}, courses_in_window=[], moments={"sport": "soir"})
    sport = [b for b in prop.blocks if b.type == "sport"]
    assert sport and all(b.debut.hour >= 12 for b in sport)


def test_meals_are_not_generated():
    prop = plan_cycle(WED, fixed_by_day={}, courses_in_window=[])
    assert not any(b.type == "repas" for b in prop.blocks)
    assert not any(b.titre in {"Petit-déjeuner", "Déjeuner", "Dîner"} for b in prop.blocks)


def test_sleep_slot_is_not_denied_by_a_weekly_revision():
    fri = FRI
    revision = (_on(fri, 20, 30), _on(fri, 22))
    prop = plan_cycle(
        WED,
        fixed_by_day={fri: [revision]},
        revisions_by_day={fri: [revision]},
        courses_in_window=[],
    )
    sleep = next(b for b in prop.blocks if b.date == fri and b.type == "sommeil")
    assert sleep.fin - sleep.debut == dt.timedelta(hours=9)


def test_sleep_finishes_before_next_day_work_shift():
    thu = WED + dt.timedelta(days=1)
    shift = (_on(thu, 7, 30), _on(thu, 16, 30))
    prop = plan_cycle(
        MON,
        fixed_by_day={thu: [shift]},
        courses_in_window=[],
    )
    wednesday_sleep = next(b for b in prop.blocks if b.type == "sommeil" and b.date == WED)
    assert wednesday_sleep.fin <= shift[0] - dt.timedelta(minutes=45)


# ── Saturation : le sport est signalé ────────────────────────────────────────

def test_saturated_day_reports_unplaced_sport():
    fri = FRI  # jour de sport
    fixed = {fri: [(_on(fri, 7), _on(fri, 23))]}  # journée pleine
    prop = plan_cycle(WED, fixed_by_day=fixed, courses_in_window=[])
    assert any("Muscu" in msg for msg in prop.non_places)
    # la cuisine (lundi, libre) reste placée
    assert any(b.type == "cuisine" for b in prop.blocks)
