from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest
from sqlmodel import select

from app.models.finance import BuffettRun, BuffettRunResult
from app.services.finance.buffett.champion import allocation_replacement_decision, portfolio_mode, stored_portfolio_score
from app.services.finance.buffett.reporting import persist_optimization_outcome


def _diagnostics():
    return {
        "executed_portfolio": {"score": 5.0, "objective_score": 2.0,
                               "feasible_under_current_constraints": True},
        "previous_run_champion": {
            "accepted_as_initial_incumbent": True,
            "feasible_under_current_constraints": True,
            "executed_feasible_under_current_constraints": True,
            "recomputed_executed_score": 6.0,
            "recomputed_executed_objective_score": 1.0,
        },
    }


def test_diversified_objective_improvement_is_not_vetoed_by_raw_return():
    decision = allocation_replacement_decision(_diagnostics())
    assert decision["accepted"] is True
    assert decision["reason"] == "objectif_exécutable_supérieur"


def test_equal_executable_champion_is_persisted_for_requested_run():
    diagnostics = _diagnostics()
    diagnostics["executed_portfolio"]["objective_score"] = 1.0
    assert allocation_replacement_decision(diagnostics)["reason"] == "champion_exécutable_retenu"
    assert allocation_replacement_decision(diagnostics)["accepted"] is True


@pytest.mark.parametrize("field", ["feasible_under_current_constraints", "executed_feasible_under_current_constraints"])
def test_valid_repair_replaces_infeasible_previous_champion(field):
    diagnostics = _diagnostics()
    diagnostics["previous_run_champion"][field] = False
    diagnostics["executed_portfolio"]["objective_score"] = -1.0
    assert allocation_replacement_decision(diagnostics)["accepted"] is True


@pytest.mark.parametrize("score", [None, float("nan"), float("inf")])
def test_invalid_executable_score_never_replaces_champion(score):
    diagnostics = _diagnostics()
    diagnostics["executed_portfolio"]["score"] = score
    assert allocation_replacement_decision(diagnostics)["accepted"] is False


def test_infeasible_executable_candidate_never_replaces_champion():
    diagnostics = _diagnostics()
    diagnostics["executed_portfolio"]["feasible_under_current_constraints"] = False
    assert allocation_replacement_decision(diagnostics)["accepted"] is False


@pytest.mark.parametrize("same_run", [False, True])
def test_rejected_candidate_keeps_matching_allocation_score_and_mode(mem_session, monkeypatch, same_run):
    from app.services.finance.buffett import broker_availability

    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: pd.DataFrame())
    historical = BuffettRun(
        run_date=dt.date(2026, 9, 1), statut="termine",
        params_json={"optimization": {
            "portfolio_universe": {"include_etfs": False},
            "executed_portfolio": {"score": 6.0, "objective_score": 1.0},
        }},
    )
    mem_session.add(historical)
    mem_session.commit()
    mem_session.refresh(historical)
    if same_run:
        current = historical
    else:
        current = BuffettRun(
            run_date=dt.date(2026, 9, 15), statut="termine",
            params_json={"optimization": {
                "portfolio_universe": {"include_etfs": True},
                "executed_portfolio": {"score": -50.0},
            }},
        )
        mem_session.add(current)
        mem_session.commit()
        mem_session.refresh(current)
        mem_session.add(BuffettRunResult(
            run_id=current.id, ticker="OLD_ETF", allocation_pct=100.0,
        ))
    mem_session.add(BuffettRunResult(
        run_id=historical.id, ticker="CHAMP", allocation_pct=90.0, broker_cible="IBKR",
        secteurs_extra={"allocations": [{"ticker": "CHAMP", "broker": "IBKR",
                                         "pct": 90.0, "shares": 9, "eur": 900.0}]},
    ))
    mem_session.commit()
    diagnostics = _diagnostics()
    diagnostics["executed_portfolio"]["objective_score"] = -2.0
    diagnostics["portfolio_universe"] = {
        "include_etfs": True, "previous_target_run_id": historical.id,
    }
    diagnostics["allocation_replacement"] = allocation_replacement_decision(diagnostics)

    retained, saved = persist_optimization_outcome(
        mem_session, current.id,
        [{"Ticker": "BAD", "Broker": "IBKR", "Poids total (%)": 100.0}],
        diagnostics,
    )
    mem_session.refresh(current)
    targets = {
        row.ticker: row.allocation_pct
        for row in mem_session.exec(select(BuffettRunResult).where(
            BuffettRunResult.run_id == current.id,
            BuffettRunResult.allocation_pct > 0,
        )).all()
    }
    assert targets == {"CHAMP": 90.0}
    assert retained[0]["shares"] == 9
    assert stored_portfolio_score(current) == (2, 6.0)
    assert portfolio_mode(current) == "actions_only"
    assert saved["last_optimization_attempt"]["executed_portfolio"]["objective_score"] == -2.0


def test_rejection_without_stored_champion_is_explicit_error(mem_session):
    run = BuffettRun(run_date=dt.date(2026, 9, 15))
    mem_session.add(run)
    mem_session.commit()
    mem_session.refresh(run)
    with pytest.raises(ValueError, match="Aucune allocation admissible"):
        persist_optimization_outcome(mem_session, run.id, [], {
            "allocation_replacement": {"accepted": False, "reason": "no score"},
        })


def test_rejected_candidate_is_displayable_when_previous_champion_is_only_in_workbook(mem_session):
    run = BuffettRun(run_date=dt.date(2026, 9, 15), statut="en_cours")
    mem_session.add(run)
    mem_session.commit()
    mem_session.refresh(run)
    mem_session.add(BuffettRunResult(run_id=run.id, ticker="AAPL"))
    mem_session.commit()

    diagnostics = _diagnostics()
    diagnostics["allocation_replacement"] = {
        "accepted": False,
        "reason": "objectif_exécutable_inférieur",
    }
    candidate = [{
        "Ticker": "AAPL",
        "AnalysisTicker": "AAPL",
        "Broker": "IBKR",
        "Poids total (%)": 100.0,
        "eur": 1000.0,
    }]

    retained, saved = persist_optimization_outcome(
        mem_session, run.id, candidate, diagnostics,
    )

    assert retained == candidate
    assert saved["allocation_replacement"]["fallback_persisted_candidate"] is True
    row = mem_session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == run.id)
    ).one()
    assert row.allocation_pct == 100.0
