"""Analytique budget : dépenses par catégorie + tendance mensuelle (#113)."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services.budget.analytics import (
    aggregate_expenses_by_category,
    month_keys,
)


def _tx(montant, category_id):
    return SimpleNamespace(montant=montant, category_id=category_id)


def test_aggregate_ignores_revenus_and_uses_absolute():
    txs = [_tx(-100.0, 1), _tx(-50.0, 1), _tx(2000.0, 1), _tx(-30.0, 2)]
    meta = {1: {"nom": "Épicerie", "couleur": "#22c55e"}, 2: {"nom": "Transport", "couleur": "#f59e0b"}}
    out = aggregate_expenses_by_category(txs, meta)
    # trié par montant desc : Épicerie 150, Transport 30
    assert [c["nom"] for c in out] == ["Épicerie", "Transport"]
    assert out[0]["montant"] == 150.0
    assert out[0]["couleur"] == "#22c55e"
    assert out[0]["pct"] == round(150 / 180 * 100, 1)


def test_aggregate_uncategorised_fallback():
    out = aggregate_expenses_by_category([_tx(-40.0, None)], {})
    assert out[0]["nom"] == "Sans catégorie"
    assert out[0]["category_id"] is None
    assert out[0]["pct"] == 100.0


def test_aggregate_empty():
    assert aggregate_expenses_by_category([], {}) == []


def test_month_keys_walks_back_across_year_boundary():
    keys = month_keys(dt.date(2026, 2, 15), 4)
    assert keys == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert keys[-1] == "2026-02"  # le mois courant en dernier
