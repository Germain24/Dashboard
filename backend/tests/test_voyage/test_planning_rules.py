from __future__ import annotations

import datetime as dt

from app.models.voyage import LieuVoyage
from app.services.voyage.planning_rules import (
    is_in_season,
    lock_reason,
    parse_available_months,
    route_detour_ratio,
    select_diverse_candidates,
    unlocked_levels,
)


def test_progression_unlocks_only_next_contiguous_level():
    lieux = [
        LieuVoyage(nom="Course facile", visite=True, ordre=1, progression="course"),
        LieuVoyage(nom="Course moyenne", visite=False, ordre=2, progression="course"),
        LieuVoyage(nom="Course dure", visite=False, ordre=3, progression="course"),
    ]
    levels = unlocked_levels(lieux)
    assert levels["course"] == 2
    assert lock_reason(lieux[1], levels) is None
    assert "Palier 3" in lock_reason(lieux[2], levels)


def test_season_parses_wrapped_ranges_and_filters_midpoint():
    assert parse_available_months("novembre-février") == {11, 12, 1, 2}
    lieu = LieuVoyage(nom="Neige", mois_disponibles="11-02")
    assert is_in_season(lieu, dt.date(2026, 12, 1), dt.date(2026, 12, 10))
    assert not is_in_season(lieu, dt.date(2026, 7, 1), dt.date(2026, 7, 10))


def test_candidate_selection_changes_with_budget_and_caps_hubs():
    candidates = []
    for i, cost in enumerate((300, 600, 1200, 2400)):
        candidates.append((cost, LieuVoyage(
            nom=f"L{i}", aeroport_iata=f"A{i}", pays=f"P{i}", priorite=3,
        ), 1.0))
    low = select_diverse_candidates(candidates, budget_total=900, limit=2)
    high = select_diverse_candidates(candidates, budget_total=6000, limit=2)
    assert {lieu.nom for lieu in low} != {lieu.nom for lieu in high}


def test_route_detour_ratio_rejects_opposite_side_of_world():
    yul = (45.4706, -73.7408)
    cdg = (49.0097, 2.5479)
    kef = (63.985, -22.6056)
    syd = (-33.9399, 151.1753)
    assert route_detour_ratio(yul, cdg, kef) < 1.2
    assert route_detour_ratio(yul, cdg, syd) > 3.0
