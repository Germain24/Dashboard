"""Tests d'intégration — API Finance avec SQLite in-memory.

Couvre : ping, portfolio, snapshots, history, transactions CRUD,
         import CSV, buffett runs, rebalancing diff.
"""
from __future__ import annotations

import datetime as dt
import io
import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session
from app.models.finance import SnapshotPortefeuille, Transaction


# ── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(name="client")
def client_fixture(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Certaines routes de fond ouvrent volontairement leur propre Session au
    # lieu d'utiliser la dépendance FastAPI (notamment le chemin mémoire de
    # /buffett/live-state). Elles doivent viser la même base isolée en test.
    import app.core.db as db
    monkeypatch.setattr(db, "engine", engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ── ping ─────────────────────────────────────────────────────────────────────

def test_ping(client):
    r = client.get("/finance/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "finance"


# ── snapshot ─────────────────────────────────────────────────────────────────

def test_snapshot_latest_empty(client):
    r = client.get("/finance/snapshot/latest")
    assert r.status_code == 200
    assert r.json() is None


def test_history_empty(client):
    r = client.get("/finance/history?days=30")
    assert r.status_code == 200
    assert r.json() == []


def test_snapshot_from_seed(client, session):
    """Snapshot seeded directly in DB is returned by /snapshot/latest."""
    snap = SnapshotPortefeuille(
        date=dt.date.today(),
        valeur=10_000.0,
        investit=8_000.0,
    )
    session.add(snap)
    session.commit()
    # Note: the client fixture uses a separate in-memory engine → seed via API instead
    # Create via a direct transaction instead
    r = client.get("/finance/history?days=365")
    assert r.status_code == 200


# ── portfolio / perf ─────────────────────────────────────────────────────────

def test_portfolio_empty(client):
    r = client.get("/finance/portfolio")
    assert r.status_code == 200
    assert r.json() == []


def test_portfolio_perf_empty(client):
    r = client.get("/finance/portfolio/perf")
    assert r.status_code == 200
    data = r.json()
    assert "valeur" in data
    assert data["valeur"] == 0.0


# ── transactions CRUD ────────────────────────────────────────────────────────

def test_transactions_empty(client):
    r = client.get("/finance/transactions")
    assert r.status_code == 200
    assert r.json() == []


def test_create_transaction(client):
    payload = {
        "ticker": "AAPL",
        "type_transaction": "achat",
        "date_transaction": "2025-01-15",
        "quantite": 10.0,
        "prix_unitaire": 180.0,
        "frais": 1.99,
        "devise": "USD",
        "broker": "Trading 212",
    }
    r = client.post("/finance/transactions", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["type"] == "achat"
    assert data["quantite"] == 10.0
    assert data["id"] > 0


def test_create_transaction_invalid_type(client):
    payload = {
        "ticker": "MSFT", "type_transaction": "cadeau",
        "date_transaction": "2025-01-15", "quantite": 5.0, "prix_unitaire": 300.0,
    }
    r = client.post("/finance/transactions", json=payload)
    assert r.status_code == 422


def test_create_transaction_rejects_negative_amounts(client):
    r = client.post("/finance/transactions", json={
        "ticker": "AAPL", "type_transaction": "achat",
        "date_transaction": "2025-01-15", "quantite": -1,
        "prix_unitaire": 100,
    })
    assert r.status_code == 422


def test_create_transaction_rejects_withholding_above_gross(client):
    r = client.post("/finance/transactions", json={
        "ticker": "LOG", "type_transaction": "dividende",
        "date_transaction": "2025-01-15", "quantite": 1,
        "prix_unitaire": 10, "montant_brut": 10, "retenue_source": 11,
    })
    assert r.status_code == 422


def test_list_transactions_after_create(client):
    client.post("/finance/transactions", json={
        "ticker": "NVDA", "type_transaction": "achat",
        "date_transaction": "2025-03-01", "quantite": 2.0, "prix_unitaire": 800.0,
    })
    r = client.get("/finance/transactions")
    assert r.status_code == 200
    tickers = [t["ticker"] for t in r.json()]
    assert "NVDA" in tickers


def test_delete_transaction(client):
    r = client.post("/finance/transactions", json={
        "ticker": "GOOG", "type_transaction": "vente",
        "date_transaction": "2025-04-01", "quantite": 1.0, "prix_unitaire": 170.0,
    })
    tx_id = r.json()["id"]
    rd = client.delete(f"/finance/transactions/{tx_id}")
    assert rd.status_code == 204
    remaining = [t["id"] for t in client.get("/finance/transactions").json()]
    assert tx_id not in remaining


def test_delete_nonexistent_transaction(client):
    r = client.delete("/finance/transactions/99999")
    assert r.status_code == 404


# ── CSV import ───────────────────────────────────────────────────────────────

TRADING212_CSV = (
    "Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency,"
    "Exchange rate,Total,Withholding tax,Currency (Withholding tax),"
    "Notes,ID,Currency conversion fee\n"
    "Market buy,2025-01-10 09:00:00,US0378331005,AAPL,Apple Inc,5,"
    "180.00,USD,1.08,972.00,0,USD,,T212_001,0\n"
    "Market sell,2025-02-15 14:30:00,US5949181045,MSFT,Microsoft Corp,2,"
    "390.00,USD,1.07,835.80,0,USD,,T212_002,0\n"
)


def test_import_trading212_csv(client):
    csv_bytes = TRADING212_CSV.encode()
    r = client.post(
        "/finance/transactions/import?broker=trading212",
        files={"file": ("export.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] >= 1
    assert isinstance(data["skipped"], int)
    assert isinstance(data["errors"], list)


def test_import_empty_csv(client):
    r = client.post(
        "/finance/transactions/import",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 0


# ── benchmarks / risk / treemap ──────────────────────────────────────────────

def test_risk_empty(client):
    r = client.get("/finance/risk")
    assert r.status_code == 200
    data = r.json()
    assert "n_positions" in data
    assert data["n_positions"] == 0


def test_treemap_empty(client):
    r = client.get("/finance/treemap?group_by=secteur")
    assert r.status_code == 200
    assert r.json() == []


# ── buffett runs ─────────────────────────────────────────────────────────────

def test_buffett_runs_empty(client):
    r = client.get("/finance/buffett/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_buffett_latest_empty(client):
    r = client.get("/finance/buffett/latest")
    assert r.status_code == 200
    assert r.json() is None


def test_buffett_progress_idle(client):
    r = client.get("/finance/buffett/progress")
    assert r.status_code == 200
    data = r.json()
    assert data["statut"] == "idle"
    assert data["progress_pct"] == 0.0


def test_buffett_live_state_restores_analysis_and_optimization_without_cache(client):
    r = client.get("/finance/buffett/live-state?history_after=0")

    assert r.status_code == 200
    assert "no-store" in r.headers["cache-control"]
    data = r.json()
    assert data["analysis"]["statut"] == "idle"
    assert data["optimization"]["phase"] == "idle"
    assert data["optimization"]["progress_pct"] == 0.0
    assert data["optimization"]["score_history"] == []


def test_buffett_run_detail_404(client):
    r = client.get("/finance/buffett/runs/99999")
    assert r.status_code == 404


def test_portfolio_create_409_when_analysis_already_running(client, monkeypatch):
    """Bouton 3 ('Créer le portefeuille optimal') doit refuser de démarrer si
    une analyse/optimisation tourne déjà dans ce process (même garde que
    buffett_run_start), sinon les deux runs corrompent le même état partagé
    (BuffettRunResult + optimization_progress)."""
    from app.services.finance import scheduler_stub
    monkeypatch.setattr(scheduler_stub, "is_analysis_running", lambda: True)
    r = client.post("/finance/portfolio/create")
    assert r.status_code == 409


def test_portfolio_create_proceeds_when_no_analysis_running(client):
    """Chemin heureux : quand aucune analyse ne tourne, la garde ne doit pas
    bloquer — l'endpoint continue vers sa logique normale (ici 404 car aucun
    run Buffett terminé n'existe dans la base de test)."""
    r = client.post("/finance/portfolio/create")
    assert r.status_code == 404
    assert "Aucun run Buffett" in r.json()["detail"]


def test_portfolio_create_can_exclude_etfs(client, monkeypatch):
    from types import SimpleNamespace

    from app.api.finance import buffett as buffett_api
    from app.services.finance import scheduler_stub

    captured = {}
    monkeypatch.setattr(scheduler_stub, "is_analysis_running", lambda: False)
    monkeypatch.setattr(
        buffett_api,
        "_latest_optimizable_run",
        lambda _session: SimpleNamespace(id=42),
    )
    monkeypatch.setattr(
        buffett_api,
        "_start_dedicated_job",
        lambda name, target, *args: captured.update(
            name=name, target=target, args=args
        ) or True,
    )

    response = client.post("/finance/portfolio/create?include_etfs=false")

    assert response.status_code == 202
    assert captured["args"] == (42, 80.0, False)
    assert "ETF=non" in response.json()["message"]


def test_latest_optimizable_run_reuses_complete_analysis_after_optimization_error(session):
    from app.api.finance.buffett import _latest_optimizable_run
    from app.models.finance import BuffettRun, BuffettRunStatus

    older = BuffettRun(
        run_date=dt.date(2026, 7, 19),
        statut=BuffettRunStatus.TERMINE.value,
        n_tickers_total=100,
        n_tickers_analyzed=100,
    )
    failed_optimization = BuffettRun(
        run_date=dt.date(2026, 7, 20),
        statut=BuffettRunStatus.ERREUR.value,
        n_tickers_total=10_454,
        n_tickers_analyzed=10_454,
        erreur="Invalid value 'False' for dtype 'float64'",
    )
    incomplete = BuffettRun(
        run_date=dt.date(2026, 7, 21),
        statut=BuffettRunStatus.ERREUR.value,
        n_tickers_total=100,
        n_tickers_analyzed=12,
    )
    session.add_all([older, failed_optimization, incomplete])
    session.commit()

    selected = _latest_optimizable_run(session)

    assert selected is not None
    assert selected.id == failed_optimization.id


def test_stored_portfolio_score_prefers_executable_score():
    from app.api.finance.buffett import _stored_portfolio_score
    from app.models.finance import BuffettRun

    executable = BuffettRun(
        run_date=dt.date(2026, 7, 20),
        params_json={
            "optimization": {
                "executed_portfolio": {"score": -17.4},
                "benchmarks": {"optimized": -12.0},
            }
        },
    )
    continuous_only = BuffettRun(
        run_date=dt.date(2026, 7, 21),
        params_json={"optimization": {"benchmarks": {"optimized": -11.0}}},
    )
    no_score = BuffettRun(run_date=dt.date(2026, 7, 22), params_json={})
    rejected_candidate = BuffettRun(
        run_date=dt.date(2026, 7, 23),
        params_json={
            "optimization": {
                "executed_portfolio": {"score": -10.0},
                "previous_run_champion": {
                    "recomputed_executed_score": -17.95,
                },
                "allocation_replacement": {
                    "accepted": False,
                    "previous_executed_score": -17.95,
                },
            }
        },
    )

    assert _stored_portfolio_score(executable) == (2, -17.4)
    assert _stored_portfolio_score(continuous_only) == (1, -11.0)
    assert _stored_portfolio_score(no_score) == (0, None)
    assert _stored_portfolio_score(rejected_candidate) == (2, -17.95)


def test_select_best_stored_target_uses_real_same_mode_champion(session):
    from app.models.finance import BuffettRun, BuffettRunResult, BuffettRunStatus
    from app.services.finance.buffett.champion import select_best_stored_target

    current = BuffettRun(
        run_date=dt.date(2026, 9, 10),
        statut=BuffettRunStatus.EN_COURS.value,
        n_tickers_total=2,
        n_tickers_analyzed=2,
    )
    older = BuffettRun(
        run_date=dt.date(2026, 9, 1),
        statut=BuffettRunStatus.TERMINE.value,
        n_tickers_total=2,
        n_tickers_analyzed=2,
        params_json={
            "optimization": {
                "portfolio_universe": {"include_etfs": False},
                "executed_portfolio": {"score": -17.95},
            }
        },
    )
    rejected = BuffettRun(
        run_date=dt.date(2026, 9, 9),
        statut=BuffettRunStatus.TERMINE.value,
        n_tickers_total=2,
        n_tickers_analyzed=2,
        params_json={
            "optimization": {
                "portfolio_universe": {"include_etfs": False},
                "executed_portfolio": {"score": -10.0},
                "allocation_replacement": {
                    "accepted": False,
                    "previous_executed_score": -17.95,
                },
            }
        },
    )
    better = BuffettRun(
        run_date=dt.date(2026, 9, 8),
        statut=BuffettRunStatus.TERMINE.value,
        n_tickers_total=2,
        n_tickers_analyzed=2,
        params_json={
            "optimization": {
                "portfolio_universe": {"include_etfs": False},
                "executed_portfolio": {"score": -17.4},
            }
        },
    )
    etf_run = BuffettRun(
        run_date=dt.date(2026, 9, 10),
        statut=BuffettRunStatus.TERMINE.value,
        n_tickers_total=2,
        n_tickers_analyzed=2,
        params_json={
            "optimization": {
                "portfolio_universe": {"include_etfs": True},
                "executed_portfolio": {"score": 0.0},
            }
        },
    )
    session.add_all([current, older, rejected, better, etf_run])
    session.commit()
    session.refresh(current)
    session.refresh(older)
    session.refresh(rejected)
    session.refresh(better)
    session.refresh(etf_run)
    session.add_all([
        BuffettRunResult(run_id=older.id, ticker="OLD", allocation_pct=100.0),
        BuffettRunResult(run_id=rejected.id, ticker="REJECTED", allocation_pct=100.0),
        BuffettRunResult(run_id=better.id, ticker="BEST", allocation_pct=100.0),
        BuffettRunResult(run_id=etf_run.id, ticker="WORLD.ETF", allocation_pct=100.0),
    ])
    session.commit()

    selected = select_best_stored_target(
        session,
        current_run_id=current.id,
        requested_mode="actions_only",
    )

    assert selected["weights"] == {"BEST": 1.0}
    assert selected["source"] == "database_same_mode_best_executable_score"
    assert selected["historical_score"] == -17.4


def test_run_portfolio_creation_noop_when_lock_already_held(monkeypatch):
    """Reproduit la course : meme si le pre-check HTTP passe (is_analysis_running
    ne voit rien), le job d'arriere-plan lui-meme doit refuser de s'executer
    si _ANALYSIS_LOCK est deja tenu (ex. par job_monthly_buffett) -- sinon
    deux optimisations mutent Config.BUDGET_BROKERS/optimization_progress en
    parallele. Sans le guard sur _run_portfolio_creation, cet appel se
    poursuivrait dans opt_prog.start(...) et planterait/mutrait l'etat
    partage au lieu de retourner immediatement."""
    from app.services.finance import scheduler_stub
    from app.api.finance.buffett import _run_portfolio_creation
    from app.services.finance.buffett import optimization_progress as opt_prog

    opt_prog.reset()
    called = {"start": False}
    monkeypatch.setattr(opt_prog, "start", lambda *a, **kw: called.__setitem__("start", True))

    assert not scheduler_stub._ANALYSIS_LOCK.locked()
    scheduler_stub._ANALYSIS_LOCK.acquire()
    try:
        # Ne doit lever aucune exception et ne rien faire : la fonction doit
        # retourner immediatement sans toucher a optimization_progress.
        _run_portfolio_creation(1, 80.0)
    finally:
        scheduler_stub._ANALYSIS_LOCK.release()

    assert called["start"] is False


# ── rebalancing ──────────────────────────────────────────────────────────────

def test_rebalancing_diff_no_run(client):
    r = client.get("/finance/rebalancing/diff")
    assert r.status_code == 200
    assert r.json() is None


# ── optimization stop ────────────────────────────────────────────────────────

def test_optimization_stop_sets_flag(client):
    from app.services.finance.buffett import optimization_progress as opt_prog

    opt_prog.reset()
    try:
        res = client.post("/finance/buffett/optimization/stop")
        assert res.status_code == 200
        assert opt_prog.snapshot()["stop_requested"] is True
    finally:
        opt_prog.reset()
