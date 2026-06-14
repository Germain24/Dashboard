"""Analytique budget : dépenses par catégorie + tendance mensuelle (#113)."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services.budget.analytics import (
    aggregate_expenses_by_category,
    build_annual_csv,
    detect_recurring,
    month_keys,
)


def _tx(montant, category_id):
    return SimpleNamespace(montant=montant, category_id=category_id)


def _txd(montant, marchand, date, category_id=None):
    return SimpleNamespace(montant=montant, marchand=marchand, date=date, category_id=category_id)


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


def test_build_annual_csv():
    txs = [
        _txd(-45.32, "METRO", dt.date(2026, 3, 2), category_id=1),
        _txd(2000.0, "Salaire", dt.date(2026, 1, 1), category_id=None),
    ]
    csv = build_annual_csv(txs, {1: "Épicerie"})
    lines = csv.strip().splitlines()
    assert lines[0] == "Date,Marchand,Description,Montant,Categorie,Compte"
    # trié par date : Salaire (jan) avant METRO (mars)
    assert lines[1].startswith("2026-01-01,Salaire,")
    assert "2026-03-02,METRO,,-45.32,Épicerie" in lines[2]


def test_detect_recurring_monthly_subscription():
    txs = [
        _txd(-17.99, "Netflix", dt.date(2026, 1, 5)),
        _txd(-17.99, "Netflix", dt.date(2026, 2, 4)),
        _txd(-17.99, "Netflix", dt.date(2026, 3, 6)),
        _txd(-120.0, "Épicerie Metro", dt.date(2026, 1, 10)),  # one-off
    ]
    rec = detect_recurring(txs)
    assert len(rec) == 1
    assert rec[0]["marchand"] == "Netflix"
    assert rec[0]["occurrences"] == 3
    assert rec[0]["montant_moyen"] == 17.99
    assert rec[0]["periodicite"] == "mensuel"


def test_detect_recurring_ignores_unstable_amount_and_irregular_cadence():
    # montant qui varie trop
    varying = [_txd(-10 * i, "X", dt.date(2026, m, 5)) for i, m in enumerate([1, 2, 3], start=1)]
    assert detect_recurring(varying) == []
    # cadence non mensuelle (hebdo)
    weekly = [_txd(-9.99, "Y", dt.date(2026, 1, d)) for d in (1, 8, 15)]
    assert detect_recurring(weekly) == []
    # trop peu d'occurrences
    assert detect_recurring([_txd(-5.0, "Z", dt.date(2026, 1, 1)), _txd(-5.0, "Z", dt.date(2026, 2, 1))]) == []


def test_recurring_vs_oneoff_projects_annual(monkeypatch):
    from app.services.budget.analytics import recurring_vs_oneoff
    txs = [
        # Abonnement mensuel (récurrent) : 16 × 3 mois.
        _txd(-16.0, "Spotify", dt.date(2026, 1, 5)),
        _txd(-16.0, "Spotify", dt.date(2026, 2, 5)),
        _txd(-16.0, "Spotify", dt.date(2026, 3, 5)),
        # Ponctuels.
        _txd(-50.0, "Resto", dt.date(2026, 1, 12)),
        _txd(-30.0, "Amazon", dt.date(2026, 2, 20)),
        # Revenu : ignoré.
        _txd(2000.0, "Salaire", dt.date(2026, 1, 1)),
    ]
    out = recurring_vs_oneoff(txs)
    assert out["nb_recurrents"] == 1
    assert out["recurrent_mensuel_total"] == 16.0
    assert out["projection_annuelle_recurrents"] == 192.0
    assert out["ponctuel_total"] == 80.0  # 50 + 30, revenu exclu
