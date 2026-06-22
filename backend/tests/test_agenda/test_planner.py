"""Tests logique pure planner.py — aucune dépendance DB."""

import datetime as dt

from app.services.agenda.planner import (
    Proposal,
    cycle_window,
    plan_cycle,
)

THU = dt.date(2026, 6, 11)  # jeudi
SUN = dt.date(2026, 6, 14)  # dimanche


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

def test_window_thursday():
    assert cycle_window(THU) == (dt.date(2026, 6, 12), dt.date(2026, 6, 14))


def test_window_sunday():
    assert cycle_window(SUN) == (dt.date(2026, 6, 15), dt.date(2026, 6, 18))


def test_run_day_never_in_window():
    start, end = cycle_window(THU)
    assert start > THU


# ── Cycle vide (tout rentre) ─────────────────────────────────────────────────

def test_empty_cycle_counts():
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=[])
    t = _types(prop)
    assert t["sommeil"] == 3            # ven, sam, dim
    assert t["repas"] == 9              # 3 jours x 3
    assert t["cuisine"] == 1           # dimanche (jour cuisine de la fenêtre)
    assert t.get("revision", 0) == 0   # aucun cours
    assert t["sport"] == 2             # ven, sam (dim = repos)
    assert prop.non_places == []


def test_cuisine_on_cooking_day():
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=[])
    cuisine = [b for b in prop.blocks if b.type == "cuisine"]
    assert len(cuisine) == 1
    assert cuisine[0].date == dt.date(2026, 6, 14)  # dimanche
    assert (cuisine[0].fin - cuisine[0].debut) == dt.timedelta(minutes=120)


def test_revision_one_block_per_course():
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=["Maths", "Physique"])
    rev = [b for b in prop.blocks if b.type == "revision"]
    assert len(rev) == 2
    assert prop.non_places == []


def test_no_block_overlaps_within_day():
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=["Maths"])
    by_day: dict[dt.date, list] = {}
    for b in prop.blocks:
        by_day.setdefault(b.date, []).append(b)
    for blocks in by_day.values():
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                assert _gap_min(blocks[i], blocks[j]) != -1, (
                    f"chevauchement {blocks[i].titre} / {blocks[j].titre}"
                )


def test_buffer_15min_around_flexible_blocks():
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=["Maths"])
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
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=[], sport_weekdays={4})
    assert _types(prop)["sport"] == 1   # ven seulement (sam, dim exclus)


def test_etudes_from_weekly_target():
    # 180 min d'objectif → 2 blocs d'études de 90 min.
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=[], etudes_target_min=180)
    etudes = [b for b in prop.blocks if b.type == "etudes"]
    assert len(etudes) == 2
    assert sum((b.fin - b.debut).total_seconds() / 60 for b in etudes) == 180


def test_sport_prefers_morning_when_free():
    prop = plan_cycle(THU, fixed_by_day={}, courses_in_window=[])
    sport = [b for b in prop.blocks if b.type == "sport"]
    assert sport and all(b.debut.hour < 12 for b in sport)   # matin de préférence


# ── Repas peuvent chevaucher le travail ──────────────────────────────────────

def test_meal_overlaps_work():
    fri = dt.date(2026, 6, 12)
    fixed = {fri: [(_on(fri, 8), _on(fri, 18))]}  # travail 8h-18h couvre le déjeuner
    prop = plan_cycle(THU, fixed_by_day=fixed, courses_in_window=[])
    lunch = [b for b in prop.blocks if b.date == fri and b.titre == "Déjeuner"]
    assert len(lunch) == 1
    assert lunch[0].debut == _on(fri, 12, 30)  # placé malgré le travail


# ── Saturation : le sport est signalé ────────────────────────────────────────

def test_saturated_day_reports_unplaced_sport():
    fri = dt.date(2026, 6, 12)  # jour de sport
    fixed = {fri: [(_on(fri, 7), _on(fri, 23))]}  # journée pleine
    prop = plan_cycle(THU, fixed_by_day=fixed, courses_in_window=[])
    assert any("Sport" in msg for msg in prop.non_places)
    # la cuisine (dimanche, libre) reste placée
    assert any(b.type == "cuisine" for b in prop.blocks)
