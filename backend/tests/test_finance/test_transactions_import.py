"""Parseur CSV Trading212 : mouvements de cash (Deposit/Withdrawal/Interest)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models.finance import Transaction
from app.services.finance.transactions import _parse_trading212_row, import_csv
from app.services.finance.portfolio_state import compute_portfolio_state


def _row(**overrides) -> dict:
    base = {
        "Action": "Deposit", "Time": "2026-01-01 13:00:14", "ISIN": "", "Ticker": "",
        "Name": "", "No. of shares": "", "Price / share": "", "Total": "50.00",
        "Currency (Total)": "EUR", "Currency conversion fee": "",
    }
    base.update(overrides)
    return base


def test_deposit_row_parses_as_depot_with_cash_ticker():
    parsed = _parse_trading212_row(_row(Action="Deposit", Total="50.00"))
    assert parsed is not None
    assert parsed["type"] == "depot"
    assert parsed["ticker"] == "CASH"
    assert parsed["quantite"] == 1.0
    assert parsed["prix_unitaire"] == 50.0
    assert parsed["date"] == dt.datetime(2026, 1, 1, 13, 0, 14)


def test_withdrawal_row_parses_as_retrait():
    parsed = _parse_trading212_row(_row(Action="Withdrawal", Total="-30.00"))
    assert parsed is not None
    assert parsed["type"] == "retrait"
    assert parsed["ticker"] == "CASH"
    assert parsed["prix_unitaire"] == 30.0  # valeur absolue, le signe vient du type


def test_interest_row_parses_as_separate_interest_income():
    parsed = _parse_trading212_row(_row(Action="Interest on cash", Total="0.01"))
    assert parsed is not None
    assert parsed["type"] == "interet"
    assert parsed["ticker"] == "CASH"
    assert parsed["prix_unitaire"] == 0.01


def test_deposit_row_not_skipped_by_import_csv_zero_quantity_filter():
    """`import_csv` écarte les lignes à quantité nulle/absente -- un Deposit
    sans ticker/quantité de titre ne doit pas tomber dans ce filtre."""
    parsed = _parse_trading212_row(_row(Action="Deposit", Total="50.00"))
    assert parsed["ticker"]  # non vide
    assert parsed["quantite"]  # non nul


def test_buy_row_derives_eur_price_from_total_not_raw_price_per_share():
    """EUR titre : Price / share et Total/qte doivent coïncider (sanity)."""
    parsed = _parse_trading212_row(_row(
        Action="Market buy", Ticker="AAPL", Total="900.00",
        **{"No. of shares": "5", "Price / share": "180.00"},
    ))
    assert parsed is not None
    assert parsed["type"] == "achat"
    assert parsed["ticker"] == "AAPL"
    assert parsed["quantite"] == 5.0
    assert parsed["prix_unitaire"] == 180.0
    assert parsed["devise"] == "EUR"


def test_buy_row_foreign_currency_uses_eur_total_not_raw_foreign_price():
    """Le bug de change : Dollarama coté 206.00 CAD, Total déjà converti par
    Trading212 = 1.54 EUR pour 0.01204429 action -> prix_unitaire doit être
    ~127.9 EUR (1.54/0.01204429), PAS 206.00 (traité comme si c'était de
    l'EUR) -- sinon cash_total/pl_latent dérivent de dizaines de milliers
    d'euros sur un compte avec plusieurs titres étrangers."""
    parsed = _parse_trading212_row(_row(
        Action="Market buy", Ticker="DOL", Total="1.54", **{"Currency (Total)": "EUR"},
        **{"No. of shares": "0.0120442900", "Price / share": "206.0000000000",
           "Currency (Price / share)": "CAD"},
    ))
    assert parsed is not None
    assert parsed["devise"] == "EUR"
    assert abs(parsed["prix_unitaire"] - (1.54 / 0.0120442900)) < 0.01
    assert parsed["prix_unitaire"] < 200  # et surtout pas 206 (le prix brut CAD)


def test_dividend_row_uses_eur_total_as_net_amount_when_no_withholding():
    parsed = _parse_trading212_row(_row(
        Action="Dividend (Dividend)", Ticker="LOG", Total="2.82",
        **{"No. of shares": "2.2761237500", "Price / share": "1.239300"},
    ))
    assert parsed is not None
    assert parsed["type"] == "dividende"
    assert parsed["quantite"] == 1.0
    assert parsed["prix_unitaire"] == 2.82


def test_dividend_row_preserves_gross_and_foreign_withholding():
    parsed = _parse_trading212_row(_row(
        Action="Dividend (Dividend)", Ticker="LOG", Total="2.82",
        **{
            "No. of shares": "2.2761237500",
            "Withholding tax": "0.66",
            "Currency (Withholding tax)": "EUR",
        },
    ))
    assert parsed is not None
    assert parsed["montant_brut"] == 3.48
    assert parsed["prix_unitaire"] == 3.48
    assert parsed["retenue_source"] == 0.66


def test_manufactured_dividend_is_marked_for_tax_allowance():
    parsed = _parse_trading212_row(_row(
        Action="Dividend (Dividend manufactured payment)", Ticker="HWKN",
        Total="0.47",
    ))
    assert parsed is not None
    assert "manufactured" in parsed["note"]


def test_trading212_total_does_not_double_count_conversion_fee():
    buy = _parse_trading212_row(_row(
        Action="Market buy", Ticker="KIROY", Total="4.98",
        **{"No. of shares": "1", "Currency conversion fee": "0.01"},
    ))
    sale = _parse_trading212_row(_row(
        Action="Market sell", Ticker="KIROY", Total="5.49",
        **{"No. of shares": "1", "Currency conversion fee": "0.01"},
    ))
    assert buy is not None and sale is not None
    assert buy["prix_unitaire"] == 4.97
    assert buy["frais"] == 0.01
    assert sale["prix_unitaire"] == 5.5
    assert sale["frais"] == 0.01

    state = compute_portfolio_state([
        _Tx("depot", "CASH", "Trading212", quantite=1, prix_unitaire=10, id=1),
        _Tx("achat", "KIROY", "Trading212", quantite=1, prix_unitaire=buy["prix_unitaire"], frais=buy["frais"], id=2),
        _Tx("vente", "KIROY", "Trading212", quantite=1, prix_unitaire=sale["prix_unitaire"], frais=sale["frais"], id=3),
    ], {}, {})
    assert state["cash_total"] == 10.51


class _Tx:
    def __init__(self, type, ticker, broker, quantite=0.0, prix_unitaire=0.0, frais=0.0, date=None, id=0):
        self.type = type
        self.ticker = ticker
        self.broker = broker
        self.quantite = quantite
        self.prix_unitaire = prix_unitaire
        self.frais = frais
        self.date = date or dt.datetime(2026, 1, 1)
        self.id = id


def test_deposit_then_buy_gives_correct_cash_and_investi_net():
    """Le bug original : sans le dépôt, cash_total dérivait très négatif et
    investi_net restait à 0 malgré de vrais achats."""
    txs = [
        _Tx("depot", "CASH", "trading212", quantite=1.0, prix_unitaire=50.0, id=1),
        _Tx("achat", "AAPL", "trading212", quantite=1.0, prix_unitaire=30.0, id=2),
    ]
    state = compute_portfolio_state(txs, {"AAPL": 35.0}, {})
    assert state["cash_total"] == 20.0  # 50 déposés - 30 dépensés
    assert state["investi_net"] == 50.0
    assert state["cash_par_broker"]["trading212"] == 20.0


# ── import_csv : dédup en cas de réimport d'un export déjà traité ───────────

TRADING212_CSV = (
    "Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency,"
    "Exchange rate,Total,Withholding tax,Currency (Withholding tax),"
    "Notes,ID,Currency conversion fee\n"
    "Market buy,2025-01-10 09:00:00,US0378331005,AAPL,Apple Inc,5,"
    "180.00,USD,1.08,972.00,0,USD,,T212_001,0\n"
    "Market sell,2025-02-15 14:30:00,US5949181045,MSFT,Microsoft Corp,2,"
    "390.00,USD,1.07,835.80,0,USD,,T212_002,0\n"
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_reimporting_same_csv_does_not_duplicate_transactions():
    """Reexporter/reimporter un CSV deja traite (cas plausible : reexport
    "tout l'historique" depuis un broker) ne doit pas dupliquer les lignes en
    base -- sinon gains/pertes realises et impot (impots_transactions.py)
    sont comptes en double."""
    session = _make_session()
    try:
        first = import_csv(session, TRADING212_CSV, broker_hint="trading212")
        assert first["imported"] > 0
        assert not first["errors"]

        second = import_csv(session, TRADING212_CSV, broker_hint="trading212")
        assert second["imported"] == 0
        assert second["skipped"] == first["imported"]

        total = len(session.exec(select(Transaction)).all())
        assert total == first["imported"]
    finally:
        session.close()


def test_reimport_matches_broker_alias_ticker_without_creating_duplicate():
    session = _make_session()
    try:
        session.add(Transaction(
            date=dt.datetime(2026, 2, 9, 14, 34, 30), ticker="SGLN.L",
            broker="Trading212", type="achat", quantite=1.42387942,
            prix_unitaire=82.14881, devise="EUR", frais=0.18,
        ))
        session.commit()
        content = (
            "Action,Time,ISIN,Ticker,Name,ID,No. of shares,Price / share,"
            "Currency (Price / share),Exchange rate,Total,Currency (Total),"
            "Currency conversion fee,Currency (Currency conversion fee)\n"
            "Market buy,2026-02-09 14:34:30,IE00B4ND3602,SGLN,Gold,ORDER1,"
            "1.4238794200,7164.00,GBX,87.34199987,116.97,EUR,0.18,EUR\n"
        )
        result = import_csv(session, content, broker_hint="trading212")
        assert result["imported"] == 0
        assert result["updated"] == 1
        rows = list(session.exec(select(Transaction)).all())
        assert len(rows) == 1
        assert rows[0].ticker == "SGLN.L"
        assert rows[0].prix_unitaire == 82.02239485
    finally:
        session.close()


def test_reimport_migrates_legacy_interest_without_duplicate():
    session = _make_session()
    try:
        session.add(Transaction(
            date=dt.datetime(2026, 1, 1, 13, 0, 14), ticker="CASH",
            broker="Trading212", type="dividende", quantite=1.0,
            prix_unitaire=0.01, devise="EUR",
        ))
        session.commit()
        content = (
            "Action,Time,Ticker,ID,No. of shares,Total,Currency (Total)\n"
            "Interest on cash,2026-01-01 13:00:14,,INT1,,0.01,EUR\n"
        )
        result = import_csv(session, content, broker_hint="trading212")
        rows = list(session.exec(select(Transaction)).all())
        assert result["imported"] == 0
        assert result["updated"] == 1
        assert len(rows) == 1
        assert rows[0].type == "interet"
    finally:
        session.close()
