"""Endpoint /finance/treemap : un ETF connu du look-through est réparti sur
ses pays/secteurs sous-jacents au lieu d'être attribué en bloc à son pays de
cotation ou groupé sous le libellé brut "ETF" (#doublon Composition)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session
from app.models.finance import BuffettRunResult, Position
from app.services.finance import prices


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c


def _seed_cw8(session):
    session.add(Position(ticker="CW8.PA", broker="t212", quantite=10, pmu=300.0, devise="EUR"))
    # Comme en prod : ETF coté à Paris -> pays="France", secteur brut="ETF".
    session.add(BuffettRunResult(ticker="CW8.PA", nom="Amundi MSCI World", pays="France", secteur="ETF"))
    session.commit()
    prices.clear_cache()
    prices.get_prices(["CW8.PA"], fetcher=lambda t: {"CW8.PA": 400.0})  # valeur = 4000


def test_treemap_pays_splits_etf_via_lookthrough(client, session, monkeypatch):
    _seed_cw8(session)
    monkeypatch.setattr(
        "app.services.finance.buffett.lookthrough.load_lookthrough",
        lambda: ({}, {"CW8.PA": {"United States": 0.7, "France": 0.3}}),
    )

    r = client.get("/finance/treemap?group_by=pays")
    assert r.status_code == 200
    nodes = r.json()
    roots = {n["label"]: n["valeur"] for n in nodes if n["parent"] == ""}
    assert roots == {"United States": 2800.0, "France": 1200.0}


def test_treemap_pays_falls_back_when_lookthrough_unavailable(client, session, monkeypatch):
    """Ticker absent du look-through (ou Excel introuvable) : on garde l'ancien
    comportement (attribution simple au pays BuffettRunResult)."""
    _seed_cw8(session)
    monkeypatch.setattr(
        "app.services.finance.buffett.lookthrough.load_lookthrough",
        lambda: ({}, {}),
    )

    r = client.get("/finance/treemap?group_by=pays")
    nodes = r.json()
    roots = {n["label"]: n["valeur"] for n in nodes if n["parent"] == ""}
    assert roots == {"France": 4000.0}


def test_treemap_secteur_uses_classification_instead_of_raw_etf_label(client, session, monkeypatch):
    _seed_cw8(session)
    monkeypatch.setattr(
        "app.services.finance.buffett.breakdown.load_classification",
        lambda: ({"CW8.PA": "Actions"}, {"CW8.PA": "Actions diversifiees"}),
    )

    r = client.get("/finance/treemap?group_by=secteur")
    nodes = r.json()
    roots = {n["label"]: n["valeur"] for n in nodes if n["parent"] == ""}
    assert roots == {"Actions diversifiees": 4000.0}
