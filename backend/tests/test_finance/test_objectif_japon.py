"""Objectif court terme Japon : réserve bancaire décroissante."""

import datetime as dt

import pytest
from pydantic import ValidationError

from app.api.finance.objectif import ObjectifJaponPatch, compute_objectif_japon


def test_objectif_japon_decreases_by_daily_budget_each_day():
    kwargs = {
        "liquidites_cad": 10_000,
        "date_cible": dt.date(2028, 9, 1),
        "budget_quotidien_cad": 65,
        "n_comptes": 4,
    }

    first = compute_objectif_japon(today=dt.date(2026, 7, 22), **kwargs)
    next_day = compute_objectif_japon(today=dt.date(2026, 7, 23), **kwargs)

    assert first["objectif_restant_cad"] - next_day["objectif_restant_cad"] == 65
    assert first["jours_restants"] == 773
    assert first["objectif_restant_cad"] == 50_245
    assert first["liquidites_cad"] == 10_000
    assert first["ecart_cad"] == -40_245
    assert first["n_comptes"] == 4


def test_objectif_japon_includes_target_date():
    result = compute_objectif_japon(
        liquidites_cad=0,
        date_cible=dt.date(2028, 9, 1),
        budget_quotidien_cad=65,
        today=dt.date(2028, 9, 1),
    )

    assert result["jours_restants"] == 1
    assert result["objectif_restant_cad"] == 65
    assert result["progression_pct"] == 0
    assert result["atteint"] is False


def test_objectif_japon_is_complete_after_target_date():
    result = compute_objectif_japon(
        liquidites_cad=0,
        date_cible=dt.date(2028, 9, 1),
        budget_quotidien_cad=65,
        today=dt.date(2028, 9, 2),
    )

    assert result["jours_restants"] == 0
    assert result["objectif_restant_cad"] == 0
    assert result["progression_pct"] == 100
    assert result["atteint"] is True


def test_objectif_japon_patch_requires_future_date():
    today = dt.date.today()

    with pytest.raises(ValidationError, match="postérieure à aujourd'hui"):
        ObjectifJaponPatch(date_cible=today, budget_quotidien_cad=65)

    patch = ObjectifJaponPatch(
        date_cible=today + dt.timedelta(days=1),
        budget_quotidien_cad=65,
    )
    assert patch.date_cible == today + dt.timedelta(days=1)
