"""Tests TDD — patrimoine net : actifs manuels (RealT) + passifs (emprunt)."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.patrimoine import PatrimoineItem  # noqa: F401 (enregistre la table)
from app.models.finance import SnapshotPortefeuille
from app.services.finance.patrimoine import (
    compute_net_worth,
    create_item,
    delete_item,
    list_items,
    net_worth_summary,
    to_eur,
    update_item,
)


def test_to_eur_noop_for_eur():
    assert to_eur(100, "EUR") == 100
    assert to_eur(100, None) == 100


def test_net_worth_converts_local_currencies(session, monkeypatch):
    # FX simulé : 1 USD = 0.9 EUR, 1 CAD = 0.7 EUR
    rates = {("USD", "EUR"): 0.9, ("CAD", "EUR"): 0.7}
    monkeypatch.setattr(
        "app.services.finance.fx.convert",
        lambda amount, base, quote: round(amount * rates[(base, quote)], 2),
    )
    create_item(session, type="actif", label="RealT", valeur=1000, categorie="RealT", devise="USD")
    create_item(session, type="actif", label="Desjardins", valeur=2000, categorie="cash", devise="CAD")
    create_item(session, type="actif", label="BanquePop", valeur=500, categorie="cash", devise="EUR")
    create_item(session, type="passif", label="Prêt", valeur=10000, categorie="emprunt", devise="EUR")
    out = net_worth_summary(session)
    # actifs EUR = 900 + 1400 + 500 = 2800 ; passifs = 10000
    assert out["actifs_manuels"] == 2800
    assert out["passifs"] == 10000
    assert out["net"] == 2800 - 10000
    realt = next(i for i in out["items"] if i["label"] == "RealT")
    assert realt["valeur_eur"] == 900  # 1000 USD × 0.9


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


# ── compute_net_worth (pur) ───────────────────────────────────────────────────

def test_net_worth_assets_minus_liabilities_plus_portfolio():
    items = [
        SimpleNamespace(type="actif", valeur=20000),   # RealT
        SimpleNamespace(type="actif", valeur=5000),     # crypto
        SimpleNamespace(type="passif", valeur=12000),   # emprunt étudiant
    ]
    out = compute_net_worth(30000, items)
    assert out["portefeuille"] == 30000
    assert out["actifs_manuels"] == 25000
    assert out["passifs"] == 12000
    assert out["net"] == 30000 + 25000 - 12000


def test_net_worth_handles_empty():
    out = compute_net_worth(0, [])
    assert out == {"portefeuille": 0, "actifs_manuels": 0, "passifs": 0, "net": 0}


# ── CRUD + intégration ────────────────────────────────────────────────────────

def test_create_and_list(session):
    create_item(session, type="actif", label="RealT — 10 tokens", valeur=520.0, categorie="RealT")
    create_item(session, type="passif", label="Prêt étudiant", valeur=12000, categorie="emprunt étudiant", taux_pct=1.5, mensualite=150)
    items = list_items(session)
    assert {i.type for i in items} == {"actif", "passif"}


def test_create_rejects_bad_type(session):
    with pytest.raises(ValueError):
        create_item(session, type="autre", label="x", valeur=1)


def test_update_and_delete(session):
    it = create_item(session, type="actif", label="RealT", valeur=500, categorie="RealT")
    update_item(session, it.id, {"valeur": 540})
    assert session.get(PatrimoineItem, it.id).valeur == 540
    assert delete_item(session, it.id) is True
    assert list_items(session) == []


def test_net_worth_summary_uses_latest_portfolio_snapshot(session):
    session.add(SnapshotPortefeuille(date=dt.date(2026, 6, 1), valeur=10000, investit=8000))
    session.add(SnapshotPortefeuille(date=dt.date(2026, 6, 10), valeur=11000, investit=8000))
    session.commit()
    create_item(session, type="actif", label="RealT", valeur=2000, categorie="RealT")
    create_item(session, type="passif", label="Prêt", valeur=12000, categorie="emprunt étudiant")
    out = net_worth_summary(session, cad_eur=1.0, inclure_portefeuille=True)
    assert out["portefeuille"] == 11000          # dernier snapshot (×1.0)
    assert out["net"] == 11000 + 2000 - 12000
    assert len(out["items"]) == 2


def test_net_worth_excludes_portfolio_by_default():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as session:
        session.add(SnapshotPortefeuille(date=dt.date(2026, 6, 10), valeur=99999, investit=8000))
        session.commit()
        create_item(session, type="actif", label="RealT", valeur=2000, categorie="RealT")
        out = net_worth_summary(session)  # défaut : portefeuille exclu
        assert out["portefeuille"] == 0
        assert out["net"] == 2000


def test_net_worth_converts_portfolio_cad_to_eur():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as session:
        session.add(SnapshotPortefeuille(date=dt.date(2026, 6, 10), valeur=10000, investit=8000))
        session.commit()
        out = net_worth_summary(session, cad_eur=0.7, inclure_portefeuille=True)
        assert out["portefeuille"] == 7000  # 10000 CAD × 0.7
        assert out["taux_cad_eur"] == 0.7
