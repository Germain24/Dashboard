"""Intégration : l'état dérivé reflète les transactions saisies (avec invalidation)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session
from app.services.finance import portfolio_state, prices


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    portfolio_state.invalidate_state()
    prices.clear_cache()
    # cours fixe pour le ticker testé
    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 120.0})
    with TestClient(app) as c:
        yield c


def test_state_reflects_transactions(client):
    # état vide
    r = client.get("/finance/state")
    assert r.status_code == 200
    assert r.json()["cash_total"] == 0.0

    # dépôt de cash
    client.post("/finance/transactions", json={
        "ticker": "CASH", "type_transaction": "depot",
        "date_transaction": "2026-06-01", "quantite": 1, "prix_unitaire": 1000,
    })
    # achat
    client.post("/finance/transactions", json={
        "ticker": "AAPL", "type_transaction": "achat",
        "date_transaction": "2026-06-02", "quantite": 5, "prix_unitaire": 100,
    })

    st = client.get("/finance/state").json()
    assert st["cash_total"] == 500.0  # 1000 - 500
    assert st["investi_net"] == 1000.0
    assert len(st["positions"]) == 1
    assert st["positions"][0]["ticker"] == "AAPL"
    assert st["positions"][0]["valeur"] == 600.0  # 5 * 120

    cash = client.get("/finance/cash").json()
    assert cash["cash_total"] == 500.0
