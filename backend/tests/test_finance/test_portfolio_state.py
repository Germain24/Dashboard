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


def test_sale_fee_reduces_realized_profit():
    txs = [
        _tx("achat", ticker="AAPL", quantite=10, prix_unitaire=100, frais=10, jour=1),
        _tx("vente", ticker="AAPL", quantite=10, prix_unitaire=120, frais=5, jour=2),
    ]
    st = compute_portfolio_state(txs, {}, TAXE)
    assert st["pl_realise"] == 185.0


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


def test_interest_increases_cash_but_not_dividend_total():
    txs = [_tx("interet", ticker="CASH", quantite=1, prix_unitaire=2.5)]
    st = compute_portfolio_state(txs, {}, TAXE)
    assert st["cash_total"] == 2.5
    assert st["dividendes_total"] == 0.0
    assert st["interets_total"] == 2.5
    assert st["revenus_mobiliers_total"] == 2.5


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


def test_state_from_positions_fallback(monkeypatch):
    """Sans transactions, l'état Suivi est dérivé de la table Position."""
    from sqlmodel import Session, SQLModel, create_engine

    import app.services.finance.prices as prices_mod
    from app.models.finance import Position
    from app.services.finance.portfolio_state import _state_from_positions

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    s = Session(engine)
    s.add(Position(ticker="CW8.PA", broker="Bourse Direct", quantite=40, pmu=375.0, devise="EUR"))
    s.commit()
    monkeypatch.setattr(prices_mod, "get_prices", lambda tickers, **k: {"CW8.PA": 668.40})

    st = _state_from_positions(s, TAXE)
    assert st["investi_net"] == 15000.0          # 375 * 40
    assert st["valeur_totale"] == 26736.0        # 668.40 * 40
    assert st["pl_latent_total"] == 11736.0      # (668.40 - 375) * 40
    assert st["cash_total"] == 0.0               # inconnu sans ledger
    assert st["pl_realise"] == 0.0
    assert st["positions"][0]["ticker"] == "CW8.PA"


def test_ledger_and_distinct_manual_positions_are_merged(monkeypatch):
    """Suivre un titre par transaction ne doit pas masquer les autres comptes."""
    from sqlmodel import Session, SQLModel, create_engine

    import app.services.finance.prices as prices_mod
    from app.models.finance import Position, Transaction
    from app.services.finance.portfolio_state import (
        get_portfolio_state,
        invalidate_state,
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Position(
                ticker="CW8.PA",
                broker="Bourse Direct",
                quantite=40,
                pmu=375.0,
                devise="EUR",
            )
        )
        session.add(
            Transaction(
                date=dt.datetime(2026, 7, 1),
                ticker="SGLN.L",
                broker="Trading212",
                type="achat",
                quantite=10,
                prix_unitaire=50.0,
                devise="EUR",
            )
        )
        session.commit()
        monkeypatch.setattr(
            prices_mod,
            "get_prices",
            lambda tickers, **kwargs: {"CW8.PA": 680.0, "SGLN.L": 60.0},
        )
        invalidate_state()

        state = get_portfolio_state(session)

        assert {position["ticker"] for position in state["positions"]} == {
            "CW8.PA",
            "SGLN.L",
        }
        assert state["valeur_totale"] == 27_300.0
        assert state["investi_net"] == 15_000.0
        invalidate_state()


def test_ledger_position_wins_over_same_manual_ticker_and_broker(monkeypatch):
    from sqlmodel import Session, SQLModel, create_engine

    import app.services.finance.prices as prices_mod
    from app.models.finance import Position, Transaction
    from app.services.finance.portfolio_state import (
        get_portfolio_state,
        invalidate_state,
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Position(
                ticker="AAPL",
                broker="Trading212",
                quantite=99,
                pmu=10.0,
                devise="EUR",
            )
        )
        session.add(
            Transaction(
                date=dt.datetime(2026, 7, 1),
                ticker="AAPL",
                broker="Trading212",
                type="achat",
                quantite=2,
                prix_unitaire=100.0,
                devise="EUR",
            )
        )
        session.commit()
        monkeypatch.setattr(
            prices_mod, "get_prices", lambda tickers, **kwargs: {"AAPL": 120.0}
        )
        invalidate_state()

        state = get_portfolio_state(session)

        assert len(state["positions"]) == 1
        assert state["positions"][0]["quantite"] == 2
        invalidate_state()


# ── open_position_tickers : ne prix que les positions ENCORE ouvertes --
# une position soldée (ex. ANTIN/LR/IPN vendues) était re-téléchargée à chaque
# rafraîchissement de l'état, en pure perte (symboles souvent invalides). ──

class _Tx:
    def __init__(self, type, ticker, quantite):
        self.type = type
        self.ticker = ticker
        self.quantite = quantite


def test_open_position_tickers_excludes_fully_sold():
    from app.services.finance.portfolio_state import open_position_tickers
    txs = [
        _Tx("achat", "AAPL", 2.0),
        _Tx("achat", "ANTIN", 1.17968264),
        _Tx("vente", "ANTIN", 1.17968264),  # soldée
        _Tx("dividende", "ANTIN", 1.0),      # dividende: pas besoin de cours
        _Tx("vente", "AAPL", 1.0),           # reste 1.0 -> ouverte
    ]
    assert open_position_tickers(txs) == {"AAPL"}


def test_open_position_tickers_ignores_cash_and_deposits():
    from app.services.finance.portfolio_state import open_position_tickers
    txs = [
        _Tx("depot", "CASH", 1.0),
        _Tx("achat", "CASH", 1.0),
        _Tx("achat", "", 1.0),
        _Tx("achat", "msft", 3.0),
    ]
    assert open_position_tickers(txs) == {"MSFT"}
