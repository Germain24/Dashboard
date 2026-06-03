"""État du portefeuille dérivé des transactions (cœur pur)."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services.finance.portfolio_state import compute_portfolio_state

TAXE = {"taux_plus_value_pct": 25.0, "taux_dividende_pct": 15.0}


def _tx(type_, ticker="", broker="t212", quantite=0.0, prix_unitaire=0.0, frais=0.0, jour=1):
    return SimpleNamespace(
        type=type_, ticker=ticker, broker=broker, quantite=quantite,
        prix_unitaire=prix_unitaire, frais=frais, date=dt.datetime(2026, 6, jour),
    )


def test_depot_then_achat_cash_and_position():
    txs = [
        _tx("depot", ticker="CASH", prix_unitaire=1000, quantite=1, jour=1),
        _tx("achat", ticker="AAPL", quantite=5, prix_unitaire=100, frais=2, jour=2),
    ]
    st = compute_portfolio_state(txs, {"AAPL": 120.0}, TAXE)
    # cash = 1000 - (5*100 + 2) = 498
    assert st["cash_total"] == 498.0
    assert st["investi_net"] == 1000.0
    pos = st["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantite"] == 5
    assert pos["acb"] == round((500 + 2) / 5, 2)  # 100.4 (frais inclus)
    assert pos["valeur"] == 600.0
    assert pos["pl_latent"] == round((120 - 100.4) * 5, 2)


def test_vente_realise_pl():
    txs = [
        _tx("achat", ticker="AAPL", quantite=10, prix_unitaire=100, jour=1),
        _tx("vente", ticker="AAPL", quantite=4, prix_unitaire=150, jour=2),
    ]
    st = compute_portfolio_state(txs, {"AAPL": 150.0}, TAXE)
    # ACB = 100 ; réalisé = (150-100)*4 = 200
    assert st["pl_realise"] == 200.0
    pos = st["positions"][0]
    assert pos["quantite"] == 6
    # cash = -1000 (achat) + 600 (vente) = -400
    assert st["cash_total"] == -400.0


def test_dividende_and_taxes():
    txs = [
        _tx("achat", ticker="AAPL", quantite=10, prix_unitaire=100, jour=1),
        _tx("vente", ticker="AAPL", quantite=10, prix_unitaire=120, jour=2),  # réalisé +200
        _tx("dividende", ticker="AAPL", quantite=10, prix_unitaire=2, jour=3),  # +20
    ]
    st = compute_portfolio_state(txs, {}, TAXE)
    assert st["pl_realise"] == 200.0
    assert st["dividendes_total"] == 20.0
    assert st["taxes"]["impot_pv"] == 50.0   # 200 * 25 %
    assert st["taxes"]["impot_div"] == 3.0   # 20 * 15 %
    assert st["taxes"]["total"] == 53.0
    assert st["positions"] == []  # tout vendu


def test_allocation_includes_cash():
    txs = [
        _tx("depot", ticker="CASH", prix_unitaire=400, quantite=1, jour=1),
        _tx("achat", ticker="AAPL", quantite=6, prix_unitaire=100, jour=2),  # cash -> -200... évitons négatif
        _tx("depot", ticker="CASH", prix_unitaire=400, quantite=1, jour=3),
    ]
    st = compute_portfolio_state(txs, {"AAPL": 100.0}, TAXE)
    # positions AAPL = 600 ; cash = 800 - 600 = 200 ; total = 800
    assert st["valeur_totale"] == 800.0
    alloc = {a["label"]: a["poids_pct"] for a in st["allocation"]}
    assert alloc["AAPL"] == 75.0
    assert alloc["Cash"] == 25.0


def test_empty():
    st = compute_portfolio_state([], {}, TAXE)
    assert st["positions"] == []
    assert st["cash_total"] == 0.0
    assert st["valeur_totale"] == 0.0
    assert st["taxes"]["total"] == 0.0
