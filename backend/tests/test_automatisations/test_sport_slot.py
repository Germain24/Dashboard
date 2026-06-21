"""Placement du sport sur un créneau libre (matin de préférence, sinon aprem/soir)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.semaine_auto import _pick_sport_slot

_D = dt.date(2026, 6, 22)


def _slot(h, duree=120):
    debut = dt.datetime.combine(_D, dt.time(h, 0))
    return {"debut": debut, "fin": debut + dt.timedelta(minutes=duree), "duree_min": duree}


def test_prefers_morning():
    # Matin dispo → choisi même si un créneau aprem existe aussi.
    assert _pick_sport_slot([_slot(14), _slot(7)], 60).hour == 7


def test_falls_back_to_afternoon_then_evening():
    # Pas de matin : aprem préféré au soir.
    assert _pick_sport_slot([_slot(19), _slot(13)], 60).hour == 13


def test_evening_when_only_evening_free():
    assert _pick_sport_slot([_slot(20)], 60).hour == 20


def test_none_when_no_slot_big_enough():
    assert _pick_sport_slot([_slot(8, duree=30)], 60) is None
