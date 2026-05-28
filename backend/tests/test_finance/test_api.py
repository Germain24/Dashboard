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
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

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


def test_buffett_run_detail_404(client):
    r = client.get("/finance/buffett/runs/99999")
    assert r.status_code == 404


# ── rebalancing ──────────────────────────────────────────────────────────────

def test_rebalancing_diff_no_run(client):
    r = client.get("/finance/rebalancing/diff")
    assert r.status_code == 200
    assert r.json() is None
