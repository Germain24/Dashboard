"""Tests du sous-module cardio (course à pied V1)."""

from __future__ import annotations

import datetime as dt
import math

from app.services.entrainement.cardio import format_pace, pace_sec_per_km


def test_pace_seconds_per_km_basic():
    # 5 km en 25 min = 1500 s → 300 s/km
    assert math.isclose(pace_sec_per_km(5.0, 1500), 300.0)


def test_pace_handles_zero_distance():
    assert pace_sec_per_km(0.0, 1500) is None
    assert pace_sec_per_km(-1.0, 1500) is None


def test_format_pace_basic():
    # 5 km en 25 min → 5:00/km
    assert format_pace(5.0, 1500) == "5:00/km"


def test_format_pace_rounding():
    # 1 km en 5 min 30 s = 330 s/km → 5:30/km
    assert format_pace(1.0, 330) == "5:30/km"


def test_format_pace_zero_distance():
    assert format_pace(0.0, 1500) is None
