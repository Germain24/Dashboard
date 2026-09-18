import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.finance.buffett.etf_research_budget import (
    BudgetClient, EtfResearchBudget, ResearchBudgetExceeded,
)
from app.services.finance.buffett.etf_index_registry import canonical_constituent_set_id as basket
from app.services.finance.buffett import etf_index_registry as registry
from app.services.finance.buffett import official_index_enrichment as indices


def test_global_claims_are_atomic_and_deduplicated():
    budget = EtfResearchBudget(funds=3)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: budget.claim("fund", str(i % 8)), range(80)))
    assert sum(results) == 3
    assert len(budget.seen["fund"]) == 3
    assert budget.claim("index", "OTHER")  # distinct allowance, same deadline


def test_request_limit_and_deadline(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.services.finance.buffett.etf_research_budget.time.monotonic", lambda: clock[0])
    budget = EtfResearchBudget(seconds=5, requests=2)
    class Client:
        def get(self, url, **kwargs):
            return kwargs["timeout"]
    http = BudgetClient(Client(), budget)
    assert http.get("first") == 5
    clock[0] += 4
    assert http.get("second") == 1
    with pytest.raises(ResearchBudgetExceeded):
        http.get("third")
    other = EtfResearchBudget(seconds=1)
    assert other.claim("fund", "one")
    clock[0] += 2
    assert not other.claim("index", "two")


@pytest.mark.parametrize("left,right", [
    ("Indice MSCI Monde rendement net", "msci World Net Return Index"),
    ("MSCI Marchés Émergents", "MSCI EM"),
    ("MSCI All Country World", "MSCI ACWI"),
    ("S & P 500", "S&P 500"),
    ("MSCI-WORLD-NET-RETURN-INDEX", "MSCI World"),
    ("MSCI World couvert en EUR", "MSCI World EUR Hedged"),
])
def test_closed_aliases(left, right):
    assert basket(left) == basket(right)
    assert basket(left, strip_hedging=False) == basket(right, strip_hedging=False)


@pytest.mark.parametrize("variant", ["ESG", "SRI", "Equal Weight", "Small Cap", "Capped", "2x", "ex USA"])
def test_strategy_variants_are_never_merged(variant):
    assert basket(f"MSCI World {variant}") != basket("MSCI World")


def test_currency_hedged_selection_stays_distinct():
    assert basket("MSCI World couvert EUR", strip_hedging=False) != basket("MSCI World", strip_hedging=False)


def test_budget_exhaustion_does_not_poison_index_retry_cache(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    registry.save_registry({"version": 2, "funds": {}, "indices": {
        "MSCI-WORLD": {"name": "MSCI World", "provider": "msci"},
    }}, path)
    budget = EtfResearchBudget(requests=1)
    def fetch(http, record):
        http.budget.before_request()
        http.budget.before_request()
    monkeypatch.setattr(indices, "_fetch_index", fetch)
    assert indices.enrich_official_indices(["MSCI-WORLD"], path=path, client=object(), budget=budget) == {}
    assert not registry.load_registry(path)["indices"]["MSCI-WORLD"].get("official_enrichment")


def test_equivalent_indices_only_get_one_network_attempt(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    registry.save_registry({"version": 2, "funds": {}, "indices": {
        "A": {"name": "MSCI Monde", "provider": "msci"},
        "B": {"name": "MSCI World", "provider": "msci"},
    }}, path)
    calls = []
    def fetch(http, record):
        calls.append(record["name"])
        return {"status": "unavailable", "last_attempt_at": dt.date.today().isoformat()}
    monkeypatch.setattr(indices, "_fetch_index", fetch)
    indices.enrich_official_indices(["A", "B"], path=path, client=object(), budget=EtfResearchBudget())
    assert len(calls) == 1


def test_cached_composition_is_reused_across_languages_but_not_conflicting_ids(tmp_path):
    composition = {"source": "official_index_constituents",
                   "updated_at": dt.date.today().isoformat(),
                   "holdings": [{"ticker": "TEST", "weight": 1.0}]}
    data = {"indices": {
        "FR": {"name": "MSCI Monde", "provider": "msci"},
        "EN": {"name": "MSCI World", "provider": "msci", "composition": composition},
        "ESG": {"name": "MSCI World ESG", "provider": "msci"},
    }}
    path = tmp_path / "registry.json"
    assert registry.cached_index_composition("FR", registry=data, path=path) == composition
    assert registry.cached_index_composition("ESG", registry=data, path=path) is None
    data["indices"]["FR"]["provider_index_id"] = "different"
    data["indices"]["EN"]["provider_index_id"] = "original"
    assert registry.cached_index_composition("FR", registry=data, path=path) is None


def test_fund_budget_is_shared_across_replacement_calls(tmp_path, monkeypatch):
    from app.services.finance.buffett import official_etf_enrichment as funds
    path = tmp_path / "registry.json"
    registry.save_registry({"version": 2, "funds": {
        "A": {"name": "Amundi A", "isin": "FR0000000001"},
        "B": {"name": "Amundi B", "isin": "FR0000000002"},
    }, "indices": {}}, path)
    budget = EtfResearchBudget(funds=1)
    calls = []
    def fetch(*args):
        calls.append(1)
        raise ResearchBudgetExceeded("stop inside connector")
    monkeypatch.setattr(funds, "_fetch_amundi_factsheet", fetch)
    for ticker in ("A", "B", "A"):
        funds._enrich_official_etfs_serial(
            [ticker], path=path, client=object(), budget=budget,
            _resolved={ticker: {"identity_key": ticker}},
        )
    assert len(calls) == 1
    assert all(not fund.get("official_enrichment") for fund in registry.load_registry(path)["funds"].values())


def test_inventory_can_be_local_only(tmp_path, monkeypatch):
    from app.services.finance.buffett import official_etf_enrichment as funds
    metadata = {"TEST": {"identity_key": "TEST", "replication": "unknown"}}
    monkeypatch.setattr(registry, "resolve_index_registry", lambda *a, **k: metadata)
    monkeypatch.setattr(funds, "enrich_official_etfs", lambda *a, **k: pytest.fail("inventory network"))
    funds.enrich_unknown_etf_replications(["TEST"], path=tmp_path / "registry.json", allow_network=False)


def test_bounded_batch_never_promotes_unverified_etfs(monkeypatch):
    import pandas as pd
    from app.services.finance.buffett import etf_composition_batches as batches
    from app.services.finance.buffett import equity_lookthrough as lookthrough
    tickers = [f"ETF{i}" for i in range(20)]
    returns = pd.DataFrame({ticker: [0.0, 0.01] for ticker in ["STOCK", *tickers]})
    frame = pd.DataFrame({"Ticker": ["STOCK", *tickers]})
    budgets = []
    def select(pool, frame, col, maximum=None, excluded_tickers=None, **kwargs):
        selected = [t for t in tickers if t not in (excluded_tickers or set())][:maximum]
        return pool[["STOCK", *selected]], frame[frame[col].isin(["STOCK", *selected])], {}
    def fetch(wanted, **kwargs):
        budgets.append(kwargs["budget"])
        return {ticker: {} for ticker in wanted}
    monkeypatch.setattr(batches, "select_etfs_per_broker", select)
    monkeypatch.setattr(lookthrough, "fetch_etf_holdings", fetch)
    monkeypatch.setattr(lookthrough, "etf_composition_quality", lambda *a, **k: {"eligible": False})
    monkeypatch.setattr(batches.Config, "ETF_MAX_CANDIDATES_PER_BROKER", 1)
    monkeypatch.setattr(batches.Config, "ETF_COMPOSITION_BATCH_BUFFER_PER_BROKER", 0)
    monkeypatch.setattr(batches.Config, "ETF_COMPOSITION_MAX_ROUNDS", 2)
    result = batches.select_verified_etfs_per_broker(
        returns, frame, "Ticker", etf_tickers=set(tickers), metadata_by_ticker={}, constituent_metadata={},
    )
    assert result.batches == 2
    assert list(result.returns.columns) == ["STOCK"]
    assert len(budgets) == 2 and budgets[0] is budgets[1]
