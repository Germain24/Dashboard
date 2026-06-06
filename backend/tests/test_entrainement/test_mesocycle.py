"""Programme périodisé / mésocycle (#110)."""

from __future__ import annotations

import datetime as dt

from app.services.entrainement.mesocycle import (
    adjust_sets,
    current,
    current_phase,
    get_state,
    start_cycle,
    stop_cycle,
)

START = dt.date(2026, 6, 1)  # un lundi


def test_phase_accumulation_first_week():
    info = current_phase(START, 4, START)
    assert info["semaine_cycle"] == 1
    assert info["phase"] == "accumulation"
    assert info["cycle_num"] == 0
    assert info["cycle_len"] == 5


def test_phase_anchored_on_monday_midweek():
    # Mercredi de la 1re semaine -> toujours semaine 1
    info = current_phase(START, 4, START + dt.timedelta(days=2))
    assert info["semaine_cycle"] == 1


def test_phase_last_accumulation_then_deload():
    acc4 = current_phase(START, 4, START + dt.timedelta(weeks=3))
    assert acc4["semaine_cycle"] == 4 and acc4["phase"] == "accumulation"
    deload = current_phase(START, 4, START + dt.timedelta(weeks=4))
    assert deload["semaine_cycle"] == 5 and deload["phase"] == "deload"


def test_phase_rolls_into_next_cycle():
    info = current_phase(START, 4, START + dt.timedelta(weeks=5))
    assert info["cycle_num"] == 1
    assert info["semaine_cycle"] == 1 and info["phase"] == "accumulation"


def test_adjust_sets_ramps_then_deloads():
    s1 = current_phase(START, 4, START)
    s2 = current_phase(START, 4, START + dt.timedelta(weeks=1))
    s4 = current_phase(START, 4, START + dt.timedelta(weeks=3))
    dl = current_phase(START, 4, START + dt.timedelta(weeks=4))
    assert adjust_sets(3, s1) == 3
    assert adjust_sets(3, s2) == 4
    assert adjust_sets(3, s4) == 6
    assert adjust_sets(4, dl) == 2          # deload ~ moitié
    assert adjust_sets(1, dl) == 1          # garde-fou >= 1
    assert adjust_sets(None, s2) is None    # slot sans cible inchangé


def test_store_start_get_stop(tmp_path):
    p = tmp_path / "meso.json"
    assert get_state(path=p) is None
    start_cycle(4, path=p, today=dt.date(2026, 6, 3))  # un mercredi
    state = get_state(path=p)
    assert state is not None
    assert state["start_date"] == "2026-06-01"  # ancré au lundi
    assert state["accumulation_weeks"] == 4
    stop_cycle(path=p)
    assert get_state(path=p) is None


def test_current_merges_phase(tmp_path):
    p = tmp_path / "meso.json"
    start_cycle(4, path=p, today=START)
    cur = current(path=p, today=START + dt.timedelta(weeks=4))
    assert cur is not None
    assert cur["active"] is True
    assert cur["phase"] == "deload"
    assert cur["semaine_cycle"] == 5
