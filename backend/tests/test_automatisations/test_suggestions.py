"""Tests TDD — suggestions d'automatisation apprises des habitudes (#218).

Heuristique : un événement (même titre, même jour de semaine) qui revient sur
≥ min_weeks semaines distinctes dans la fenêtre récente est un « pattern » -> on
propose de l'automatiser. Les événements déjà récurrents (recurrence_id) sont ignorés.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services.automatisations.suggestions import detect_recurring_patterns


NOW = dt.datetime(2026, 6, 15, 12, 0)  # un lundi


def ev(titre, day, hour=9, minute=0, recurrence_id=None):
    return SimpleNamespace(
        titre=titre, debut=dt.datetime.combine(day, dt.time(hour, minute)),
        recurrence_id=recurrence_id,
    )


def mondays(n):
    """n lundis consécutifs en remontant depuis le lundi précédant NOW."""
    base = dt.date(2026, 6, 8)  # lundi
    return [base - dt.timedelta(weeks=i) for i in range(n)]


def test_detects_weekly_pattern():
    events = [ev("Muscu", d, hour=18) for d in mondays(4)]
    pats = detect_recurring_patterns(events, now=NOW, min_weeks=3, lookback_weeks=8)
    assert len(pats) == 1
    p = pats[0]
    assert p["titre"] == "Muscu"
    assert p["weekday"] == 0          # lundi
    assert p["jour"] == "lundi"
    assert p["occurrences"] == 4
    assert p["heure"] == "18:00"


def test_below_threshold_is_ignored():
    events = [ev("Yoga", d) for d in mondays(2)]  # 2 semaines seulement
    assert detect_recurring_patterns(events, now=NOW, min_weeks=3, lookback_weeks=8) == []


def test_same_weekday_different_weeks_counts_distinct_weeks():
    # deux occurrences la MÊME semaine ne comptent que pour 1 semaine
    base = dt.date(2026, 6, 8)
    events = [ev("Café", base), ev("Café", base)] + [ev("Café", base - dt.timedelta(weeks=1)),
                                                      ev("Café", base - dt.timedelta(weeks=2))]
    pats = detect_recurring_patterns(events, now=NOW, min_weeks=3, lookback_weeks=8)
    assert len(pats) == 1
    assert pats[0]["occurrences"] == 3  # 3 semaines distinctes, pas 4 events


def test_recurring_events_are_skipped():
    events = [ev("Cours", d, recurrence_id=5) for d in mondays(4)]
    assert detect_recurring_patterns(events, now=NOW, min_weeks=3, lookback_weeks=8) == []


def test_outside_lookback_window_ignored():
    old = [ev("Vieux", dt.date(2026, 1, 5) - dt.timedelta(weeks=i)) for i in range(4)]
    assert detect_recurring_patterns(old, now=NOW, min_weeks=3, lookback_weeks=8) == []


def test_title_normalized_and_message_present():
    base = dt.date(2026, 6, 8)
    events = [ev("  Muscu  ", base), ev("muscu", base - dt.timedelta(weeks=1)),
              ev("MUSCU", base - dt.timedelta(weeks=2))]
    pats = detect_recurring_patterns(events, now=NOW, min_weeks=3, lookback_weeks=8)
    assert len(pats) == 1                      # regroupés malgré casse/espaces
    assert pats[0]["occurrences"] == 3
    assert "lundi" in pats[0]["message"].lower()


def test_sorted_by_occurrences_desc():
    base = dt.date(2026, 6, 9)  # mardi
    a = [ev("A", base - dt.timedelta(weeks=i)) for i in range(3)]            # 3
    b = [ev("B", base - dt.timedelta(weeks=i) + dt.timedelta(days=1)) for i in range(5)]  # 5, mercredi
    pats = detect_recurring_patterns(a + b, now=NOW, min_weeks=3, lookback_weeks=8)
    assert [p["titre"] for p in pats] == ["B", "A"]
