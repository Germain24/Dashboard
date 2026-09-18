from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.models.finance import Position
from app.models.patrimoine import PatrimoineItem
from app.services.finance import external_accounts, kraken_api, prices


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_kraken_asset_codes_and_balance_suffixes_are_merged(monkeypatch):
    monkeypatch.setattr(
        kraken_api, "private", lambda method: {"XXBT": "1.2", "XXBT.F": "0.3", "ZEUR": "10"}
    )
    assert kraken_api.balances() == {"BTC": 1.5, "EUR": 10.0}


def test_metamask_sync_separates_networks_and_forces_realt_to_zero(monkeypatch, tmp_path):
    prices.clear_cache()
    monkeypatch.setattr(settings, "metamask_ethereum_address", "0xabc")
    monkeypatch.setattr(settings, "metamask_gnosis_address", "0xabc")
    monkeypatch.setattr(settings, "metamask_bitcoin_address", "bc1abc")

    def fake_chain(network, _url, _address):
        if network == "Ethereum":
            return ([{"ticker": "ETH", "quantity": 2.0, "price": 3_000.0}], 6_000.0)
        return ([{
            "ticker": "REALT-TEST", "quantity": 10.0, "price": 0.0,
            "realt": True, "contract": "0xRealT",
        }], 0.0)

    monkeypatch.setattr(external_accounts, "_blockscout", fake_chain)
    monkeypatch.setattr(external_accounts, "_realt_cost_basis", lambda _address: {"0xrealt": 40.0})
    monkeypatch.setattr(external_accounts, "_rmm_positions", lambda _address: [])
    monkeypatch.setattr(
        external_accounts, "_bitcoin",
        lambda _address: ([{"ticker": "BTC", "quantity": 0.1, "price": 50_000.0}], 5_000.0),
    )
    balances = {}
    monkeypatch.setattr(
        "app.services.finance.account_balances.set_balance",
        lambda account, value, **kwargs: balances.update({account: value}),
    )

    with _session() as session:
        result = external_accounts.refresh_metamask(session)
        session.commit()
        rows = list(session.exec(select(Position)).all())
        assert {(row.ticker, row.broker) for row in rows} == {
            ("ETH", "MetaMask · Ethereum"),
            ("REALT-TEST", "MetaMask · Gnosis"),
            ("BTC", "MetaMask · Bitcoin"),
        }
        assert session.exec(select(PatrimoineItem).where(PatrimoineItem.label == "MetaMask")).first()
        realt = next(row for row in rows if row.ticker == "REALT-TEST")
        assert realt.pmu == 40.0
    assert result == {
        "value_eur": 11_000.0,
        "networks": 3,
        "realt_cost_basis_eur": 400.0,
        "rmm_supply_eur": 0.0,
        "rmm_debt_eur": 0.0,
        "errors": [],
    }
    assert balances["metamask"] == 11_000.0
    assert prices.get_price("REALT-TEST", fetcher=lambda _: {"REALT-TEST": 99}) == 0.0
