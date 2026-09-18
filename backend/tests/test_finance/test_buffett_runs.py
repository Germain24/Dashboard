"""Suppression d'un run Buffett (analyse bloquée) — run + résultats."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.finance import BuffettRun, BuffettRunResult, BuffettRunStatus
from app.services.finance.buffett.reporting import (
    archive_legacy_run,
    delete_run,
    get_latest_result_for_ticker,
    get_latest_results_by_ticker,
    update_allocations,
    update_run_buy_signal_diagnostics,
    update_run_optimization_diagnostics,
    update_run_progress,
    top_company_results,
    upsert_result,
)


def _fk_engine():
    """SQLite avec FK ACTIVÉES (comme en prod) — sinon le test ne reproduit pas
    la contrainte qui faisait échouer delete_run."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    return engine


def test_buffett_run_status_values_are_stable_contract():
    assert BuffettRunStatus.EN_COURS.value == "en_cours"
    assert BuffettRunStatus.TERMINE.value == "termine"
    assert BuffettRunStatus.INTERROMPU.value == "interrompu"
    assert BuffettRunStatus.ERREUR.value == "erreur"
    assert BuffettRun(run_date=dt.date.today()).statut == "en_cours"


def test_legacy_run_can_only_be_archived_after_completion():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="en_cours")
        s.add(run)
        s.commit()
        s.refresh(run)
        with pytest.raises(RuntimeError, match="pas terminé"):
            archive_legacy_run(s, run.id)
        run.statut = "termine"
        s.add(run)
        s.commit()
        assert archive_legacy_run(s, run.id) is True
        s.refresh(run)
        assert run.params_json["archived_legacy"] is True
        assert run.params_json["comparable"] is False


def test_progress_replaces_raw_total_with_filtered_broker_total():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(
            run_date=dt.date.today(),
            n_tickers_total=10_490,
            n_tickers_analyzed=0,
            progress_pct=0.0,
        )
        s.add(run)
        s.commit()
        s.refresh(run)

        update_run_progress(s, run.id, n_done=10_454, n_total=10_454)

        refreshed = s.get(BuffettRun, run.id)
        assert refreshed is not None
        assert refreshed.n_tickers_total == 10_454
        assert refreshed.n_tickers_analyzed == 10_454
        assert refreshed.progress_pct == 100.0


def test_top_results_are_deduplicated_at_company_level_and_flag_mismatch():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(run_date=dt.date.today())
        s.add(run)
        s.commit()
        s.refresh(run)
        for ticker, quality in (("AAPL", 88.0), ("APC.DE", 81.0)):
            s.add(BuffettRunResult(
                run_id=run.id,
                ticker=ticker,
                nom="Apple Inc.",
                chance_moat=80.0,
                secteurs_extra={
                    "scores": {"model_version": 3, "buffett_quality_score": quality},
                    "entity": {
                        "company_id": "US0378331005",
                        "fundamentals_symbol": "AAPL",
                        "quote_symbol": ticker,
                    },
                },
            ))
        s.commit()

        rows = top_company_results(s, run.id)

        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"
        entity = rows[0].secteurs_extra["entity"]
        assert entity["listings"] == ["AAPL", "APC.DE"]
        assert entity["flag"] == "FUNDAMENTAL_MISMATCH"


def test_optimization_diagnostics_are_persisted_with_readable_benchmarks():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(
            run_date=dt.date.today(),
            params_json={"csv_path": "tickers.csv"},
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        diagnostics = {
            "seed": 42,
            "benchmarks": {
                "optimized": 1.23456,
                "equal_weight": 0.98765,
                "best_single_ticker": "CW8.PA",
                "best_single": 1.11111,
            },
        }

        update_run_optimization_diagnostics(s, run.id, diagnostics)

        refreshed = s.get(BuffettRun, run.id)
        assert refreshed is not None
        assert refreshed.params_json["csv_path"] == "tickers.csv"
        assert refreshed.params_json["optimization"] == diagnostics
        assert refreshed.resume == (
            "score vs CW8.PA +1.23 pts · équipondéré +0.99 "
            "· meilleur candidat simple CW8.PA +1.11"
        )


def test_buy_signal_diagnostics_are_persisted_without_erasing_run_params():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(
            run_date=dt.date.today(),
            params_json={"csv_path": "tickers.csv", "optimization": {"seed": 42}},
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        diagnostics = {
            "method": "sector_percentile",
            "percentile": 0.5,
            "excluded_missing_peg": 12,
        }

        update_run_buy_signal_diagnostics(s, run.id, diagnostics)

        refreshed = s.get(BuffettRun, run.id)
        assert refreshed is not None
        assert refreshed.params_json["csv_path"] == "tickers.csv"
        assert refreshed.params_json["optimization"] == {"seed": 42}
        assert refreshed.params_json["buy_signal"] == diagnostics


def test_delete_run_removes_run_and_its_results():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="interrompu")
        s.add(run)
        s.commit()
        s.refresh(run)
        s.add(BuffettRunResult(run_id=run.id, ticker="AAPL", chance_moat=80.0))
        s.commit()

        assert delete_run(s, run.id) is True
        assert s.get(BuffettRun, run.id) is None
        assert s.exec(select(BuffettRunResult).where(BuffettRunResult.run_id == run.id)).all() == []


def test_delete_run_returns_false_when_absent():
    with Session(_fk_engine()) as s:
        assert delete_run(s, 9999) is False


def test_same_ticker_is_persisted_independently_for_each_run():
    engine = _fk_engine()
    with Session(engine) as s:
        run_1 = BuffettRun(run_date=dt.date(2026, 7, 1), statut="termine")
        run_2 = BuffettRun(run_date=dt.date(2026, 7, 2), statut="termine")
        s.add(run_1)
        s.add(run_2)
        s.commit()
        s.refresh(run_1)
        s.refresh(run_2)

        upsert_result(s, run_1.id, "AAPL", 80.0, {"Nom": "Apple run 1"})
        upsert_result(s, run_2.id, "AAPL", 91.0, {"Nom": "Apple run 2"})

        rows = list(
            s.exec(
                select(BuffettRunResult)
                .where(BuffettRunResult.ticker == "AAPL")
                .order_by(BuffettRunResult.run_id)
            ).all()
        )
        assert [(row.run_id, row.chance_moat) for row in rows] == [
            (run_1.id, 80.0),
            (run_2.id, 91.0),
        ]


def test_upsert_normalizes_missing_country_and_sector():
    engine = _fk_engine()
    with Session(engine) as session:
        run = BuffettRun(run_date=dt.date.today(), statut="en_cours")
        session.add(run)
        session.commit()
        session.refresh(run)

        upsert_result(session, run.id, "UNKNOWN", 12.0, {"Nom": "Unknown"})

        result = session.exec(
            select(BuffettRunResult).where(BuffettRunResult.run_id == run.id)
        ).one()
        assert result.pays == "Inconnu"
        assert result.secteur == "Inconnu"


def test_latest_result_uses_newest_completed_run_and_ignores_interrupted_run():
    engine = _fk_engine()
    with Session(engine) as s:
        older = BuffettRun(run_date=dt.date(2026, 7, 1), statut="termine")
        latest = BuffettRun(run_date=dt.date(2026, 7, 2), statut="termine")
        interrupted = BuffettRun(run_date=dt.date(2026, 7, 3), statut="interrompu")
        s.add(older)
        s.add(latest)
        s.add(interrupted)
        s.commit()
        s.refresh(older)
        s.refresh(latest)
        s.refresh(interrupted)

        s.add(BuffettRunResult(run_id=older.id, ticker="AAPL", chance_moat=70.0))
        s.add(BuffettRunResult(run_id=latest.id, ticker="AAPL", chance_moat=90.0))
        s.add(BuffettRunResult(run_id=interrupted.id, ticker="AAPL", chance_moat=10.0))
        s.commit()

        result = get_latest_result_for_ticker(s, "aapl")
        assert result is not None
        assert result.run_id == latest.id
        assert result.chance_moat == 90.0


def test_latest_results_fall_back_to_legacy_rows_per_ticker():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(run_date=dt.date(2026, 7, 2), statut="termine")
        s.add(run)
        s.commit()
        s.refresh(run)
        s.add(BuffettRunResult(run_id=run.id, ticker="AAPL", chance_moat=90.0))
        s.add(BuffettRunResult(ticker="MSFT", chance_moat=80.0))
        s.commit()

        results = get_latest_results_by_ticker(s, ["aapl", "msft", "absent"])
        assert set(results) == {"AAPL", "MSFT"}
        assert results["AAPL"].run_id == run.id
        assert results["MSFT"].run_id is None


def test_allocation_update_is_scoped_to_requested_run():
    engine = _fk_engine()
    with Session(engine) as s:
        run_1 = BuffettRun(run_date=dt.date(2026, 7, 1), statut="termine")
        run_2 = BuffettRun(run_date=dt.date(2026, 7, 2), statut="termine")
        s.add(run_1)
        s.add(run_2)
        s.commit()
        s.refresh(run_1)
        s.refresh(run_2)
        s.add(BuffettRunResult(run_id=run_1.id, ticker="AAPL"))
        s.add(BuffettRunResult(run_id=run_2.id, ticker="AAPL"))
        s.commit()

        update_allocations(
            s,
            run_2.id,
            [{
                "Ticker": "AAPL",
                "Broker": "Trading212",
                "shares": None,
                "eur": 500.0,
                "prix": 200.0,
                "type": "pie",
                "Poids total (%)": 12.5,
            }],
        )

        first = s.exec(
            select(BuffettRunResult).where(BuffettRunResult.run_id == run_1.id)
        ).one()
        second = s.exec(
            select(BuffettRunResult).where(BuffettRunResult.run_id == run_2.id)
        ).one()
        assert first.allocation_pct is None
        assert second.allocation_pct == 12.5


def test_delete_run_bulk_removes_many_results():
    """Suppression en masse : un run avec beaucoup de résultats doit partir d'un
    seul DELETE (pas 1 par ligne) — c'est ce qui tenait le verrou trop longtemps
    et provoquait 'database is locked' en prod pendant qu'un run écrivait."""
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="interrompu")
        s.add(run)
        s.commit()
        s.refresh(run)
        for i in range(500):
            s.add(BuffettRunResult(run_id=run.id, ticker=f"T{i}", chance_moat=1.0))
        s.commit()

        assert delete_run(s, run.id) is True
        assert s.get(BuffettRun, run.id) is None
        assert (
            s.exec(select(BuffettRunResult).where(BuffettRunResult.run_id == run.id)).all()
            == []
        )
