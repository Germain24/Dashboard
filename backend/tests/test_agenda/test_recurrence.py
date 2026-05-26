"""Tests logique pure recurrence.py — aucune dépendance DB."""

import datetime as dt
import pytest

from app.services.agenda.recurrence import expand_rule, expand_rules_for_window


def test_expand_rule_basic():
    """Cours lun-mer-ven 09h-12h pendant 1 semaine."""
    occs = expand_rule(
        rule_id=1,
        titre="INF1000",
        weekdays=[0, 2, 4],  # Lun, Mer, Ven
        start_time="09:00",
        end_time="12:00",
        from_date=dt.date(2026, 9, 7),   # Lundi
        to_date=dt.date(2026, 9, 13),    # Dimanche
    )
    assert len(occs) == 3
    days = [o["debut"].weekday() for o in occs]
    assert days == [0, 2, 4]


def test_expand_rule_start_time():
    """L'heure de début est bien appliquée."""
    occs = expand_rule(
        rule_id=1, titre="X", weekdays=[1],
        start_time="13:30", end_time="16:30",
        from_date=dt.date(2026, 9, 8),
        to_date=dt.date(2026, 9, 8),
    )
    assert len(occs) == 1
    assert occs[0]["debut"].hour == 13
    assert occs[0]["debut"].minute == 30
    assert occs[0]["fin"].hour == 16


def test_expand_rule_until_respected():
    """La règle s'arrête à `until`."""
    occs = expand_rule(
        rule_id=1, titre="Y", weekdays=[0, 1, 2, 3, 4],
        start_time="09:00", end_time="10:00",
        from_date=dt.date(2026, 9, 7),
        to_date=dt.date(2026, 9, 20),
        until=dt.date(2026, 9, 9),  # Mercredi
    )
    # Lun 7, Mar 8, Mer 9
    assert len(occs) == 3
    assert all(o["debut"].date() <= dt.date(2026, 9, 9) for o in occs)


def test_expand_rule_no_match():
    """Fenêtre sans le bon weekday → liste vide."""
    occs = expand_rule(
        rule_id=1, titre="Z", weekdays=[6],  # Dimanche
        start_time="10:00", end_time="11:00",
        from_date=dt.date(2026, 9, 7),  # Lundi
        to_date=dt.date(2026, 9, 12),   # Samedi
    )
    assert occs == []


def test_expand_rule_is_virtual():
    """Les occurrences sont marquées is_virtual=True."""
    occs = expand_rule(
        rule_id=5, titre="Shift", weekdays=[5],
        start_time="10:00", end_time="18:00",
        from_date=dt.date(2026, 9, 12),
        to_date=dt.date(2026, 9, 12),
    )
    assert len(occs) == 1
    assert occs[0]["is_virtual"] is True
    assert occs[0]["id"] is None
    assert occs[0]["recurrence_id"] == 5


def test_expand_rules_for_window():
    """Expansion de plusieurs règles simultanées."""
    class FakeRule:
        def __init__(self, id, titre, weekdays, start_time, end_time):
            self.id = id
            self.titre = titre
            self.weekdays = weekdays
            self.start_time = start_time
            self.end_time = end_time
            self.until = None
            self.lieu = None
            self.description = None
            self.categorie = None
            self.couleur = None

    rules = [
        FakeRule(1, "INF1000", [0, 2, 4], "09:00", "12:00"),  # 3 occ
        FakeRule(2, "Shift", [5], "10:00", "18:00"),            # 1 occ
    ]
    occs = expand_rules_for_window(
        rules,
        from_date=dt.date(2026, 9, 7),
        to_date=dt.date(2026, 9, 13),
    )
    assert len(occs) == 4
    titres = {o["titre"] for o in occs}
    assert titres == {"INF1000", "Shift"}
