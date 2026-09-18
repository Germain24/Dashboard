"""Repli 'valeur du jour dérivée du ledger' pour Trading212 quand aucun PDF
Activity Statement n'est disponible (relevés remplacés par un export CSV)."""

from __future__ import annotations

import datetime as dt

from app.services.finance.account_history import t212_value_from_state


def _state(cash_par_broker, positions):
    return {"cash_par_broker": cash_par_broker, "positions": positions}


def test_sums_cash_and_position_values_for_trading212_only():
    state = _state(
        {"Trading212": 100.0, "BoursDirect2": 500.0},
        [
            {"broker": "Trading212", "valeur": 861.54},
            {"broker": "BoursDirect2", "valeur": 2000.0},
        ],
    )
    date, value = t212_value_from_state(state, today=dt.date(2026, 7, 11))
    assert date == dt.date(2026, 7, 11)
    assert value == 961.54


def test_zero_cash_and_no_positions_gives_zero():
    state = _state({}, [])
    _, value = t212_value_from_state(state, today=dt.date(2026, 7, 11))
    assert value == 0.0


def test_negative_cash_still_summed_correctly():
    state = _state({"Trading212": -7.17}, [{"broker": "Trading212", "valeur": 861.54}])
    _, value = t212_value_from_state(state, today=dt.date(2026, 7, 11))
    assert value == 854.37


def test_defaults_to_today_when_date_not_given():
    state = _state({"Trading212": 10.0}, [])
    date, _ = t212_value_from_state(state)
    assert date == dt.date.today()
