import numpy as np
import pandas as pd


def test_index_representatives_are_selected_before_history_by_replication_and_aum(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import (
        select_index_representatives_before_history,
    )

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"A": 1000.0, "B": 1000.0})
    frame = pd.DataFrame([
        {"Ticker Yahoo Finance": "ACTION", "Secteur": "Technology", "A": True, "B": True},
        {"Ticker Yahoo Finance": "PHYS_SMALL", "Secteur": "ETF", "Encours": 10, "Volume": 10, "A": True, "B": False},
        {"Ticker Yahoo Finance": "PHYS_BIG", "Secteur": "ETF", "Encours": 100, "Volume": 5, "A": True, "B": True},
        {"Ticker Yahoo Finance": "SWAP_HUGE", "Secteur": "ETF", "Encours": 10000, "Volume": 100, "A": True, "B": True},
        {"Ticker Yahoo Finance": "B_ONLY", "Secteur": "ETF", "Encours": 20, "Volume": 20, "A": False, "B": True},
    ])
    metadata = {
        "PHYS_SMALL": {"index_name": "MSCI World", "replication": "physical"},
        "PHYS_BIG": {"index_name": "MSCI World", "replication": "physical"},
        "SWAP_HUGE": {"index_name": "MSCI World", "replication": "synthetic"},
        "B_ONLY": {"index_name": "S&P 500", "replication": "physical"},
    }

    selected, filtered, diagnostics = select_index_representatives_before_history(
        frame,
        metadata,
        etf_tickers=set(metadata),
    )

    assert selected == {"PHYS_BIG", "B_ONLY"}
    assert set(filtered["Ticker Yahoo Finance"]) == {"ACTION", "PHYS_BIG", "B_ONLY"}
    assert bool(filtered.loc[filtered["Ticker Yahoo Finance"] == "PHYS_BIG", "A"].iloc[0])
    assert bool(filtered.loc[filtered["Ticker Yahoo Finance"] == "PHYS_BIG", "B"].iloc[0])
    assert diagnostics["method"] == "one_etf_per_exact_index_and_broker_before_history"


def test_index_representative_failure_promotes_next_same_index(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import (
        select_index_representatives_before_history,
    )

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"A": 1000.0})
    frame = pd.DataFrame([
        {"Ticker Yahoo Finance": "PHYS", "Secteur": "ETF", "Encours": 100, "A": True},
        {"Ticker Yahoo Finance": "SWAP", "Secteur": "ETF", "Encours": 1000, "A": True},
    ])
    metadata = {
        "PHYS": {"index_name": "CAC 40", "replication": "physical"},
        "SWAP": {"index_name": "CAC 40", "replication": "synthetic"},
    }

    first, _, _ = select_index_representatives_before_history(
        frame, metadata, etf_tickers=set(metadata)
    )
    second, _, _ = select_index_representatives_before_history(
        frame, metadata, etf_tickers=set(metadata), excluded_tickers=first
    )

    assert first == {"PHYS"}
    assert second == {"SWAP"}


def test_index_representatives_skip_unresolved_indices_before_history(monkeypatch):
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import (
        select_index_representatives_before_history,
    )

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"A": 1000.0})
    frame = pd.DataFrame([
        {"Ticker Yahoo Finance": "ACTION", "Secteur": "Technology", "A": True},
        {"Ticker Yahoo Finance": "MYSTERY", "Secteur": "ETF", "A": True},
    ])

    selected, filtered, diagnostics = select_index_representatives_before_history(
        frame, {"MYSTERY": {"replication": "unknown"}}, etf_tickers={"MYSTERY"}
    )

    assert selected == set()
    assert list(filtered["Ticker Yahoo Finance"]) == ["ACTION"]
    assert diagnostics["unresolved_indices"] == ["MYSTERY"]


def test_current_target_weights_are_read_as_fractions():
    from app.services.finance.buffett.broker_availability import current_target_weights

    frame = pd.DataFrame({
        "Ticker Yahoo Finance": ["A", "B", "A"],
        "Poids": [25.0, 0.0, 5.0],
    })

    assert current_target_weights(frame) == {"A": 0.30}


def test_etf_selection_caps_each_broker_and_keeps_actions_and_holdings(monkeypatch):
    from app.services.finance.buffett import dedup
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import select_etfs_per_broker

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"A": 1000.0, "B": 1000.0})
    monkeypatch.setattr(Config, "ETF_SELECTION_CORRELATION_DAYS", 100)
    monkeypatch.setattr(dedup, "returns_in_base_currency", lambda values, _base="EUR": values)

    etfs = ["WORLD", "USA", "EUROPE", "EM", "GOLD", "BONDS", "TECH", "HELD"]
    actions = ["META", "NVDA"]
    rng = np.random.default_rng(8)
    common = rng.normal(0, 0.01, 160)
    values = {
        "WORLD": common + rng.normal(0, 0.001, 160),
        "USA": common + rng.normal(0, 0.001, 160),
        "EUROPE": 0.7 * common + rng.normal(0, 0.004, 160),
        "EM": 0.5 * common + rng.normal(0, 0.006, 160),
        "GOLD": -0.2 * common + rng.normal(0, 0.007, 160),
        "BONDS": -0.1 * common + rng.normal(0, 0.003, 160),
        "TECH": 0.9 * common + rng.normal(0, 0.003, 160),
        "HELD": rng.normal(0, 0.008, 160),
        "META": common + rng.normal(0, 0.01, 160),
        "NVDA": common + rng.normal(0, 0.012, 160),
    }
    returns = pd.DataFrame(values)
    names = {
        "WORLD": "MSCI World ETF",
        "USA": "S&P 500 ETF",
        "EUROPE": "Europe ETF",
        "EM": "Emerging Markets ETF",
        "GOLD": "Physical Gold ETF",
        "BONDS": "Government Bond ETF",
        "TECH": "Technology ETF",
        "HELD": "Special Strategy ETF",
    }
    rows = []
    for i, ticker in enumerate(etfs):
        rows.append({
            "Ticker Yahoo Finance": ticker,
            "Nom": names[ticker],
            "Secteur": "ETF",
            "Volume": 1000 + i * 100,
            "Poids": 5.0 if ticker == "HELD" else 0.0,
            "A": True,
            "B": ticker in {"WORLD", "GOLD", "BONDS", "HELD"},
        })
    for ticker in actions:
        rows.append({
            "Ticker Yahoo Finance": ticker,
            "Nom": ticker,
            "Secteur": "Technology",
            "Volume": 5000,
            "Poids": 0.0,
            "A": True,
            "B": True,
        })
    frame = pd.DataFrame(rows)

    selected_returns, selected_frame, diagnostics = select_etfs_per_broker(
        returns, frame, maximum=3
    )

    assert {"META", "NVDA"} <= set(selected_returns.columns)
    assert "HELD" in diagnostics["brokers"]["A"]["selected_tickers"]
    assert "HELD" in diagnostics["brokers"]["B"]["selected_tickers"]
    assert diagnostics["brokers"]["A"]["selected"] == 3
    assert diagnostics["brokers"]["B"]["selected"] == 3
    assert len(selected_returns.columns) < len(returns.columns)
    assert set(selected_frame["Ticker Yahoo Finance"]) == set(selected_returns.columns)


def test_etf_selection_accepts_excel_float64_broker_columns(monkeypatch):
    """Régression pandas 3 : False ne peut pas être écrit dans une colonne float64."""
    from app.services.finance.buffett import dedup
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import select_etfs_per_broker

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    monkeypatch.setattr(Config, "ETF_SELECTION_CORRELATION_DAYS", 60)
    monkeypatch.setattr(dedup, "returns_in_base_currency", lambda values, _base="EUR": values)

    rng = np.random.default_rng(47)
    returns = pd.DataFrame({
        "WORLD": rng.normal(0, 0.01, 80),
        "BONDS": rng.normal(0, 0.004, 80),
        "TECH": rng.normal(0, 0.02, 80),
    })
    frame = pd.DataFrame({
        "Ticker Yahoo Finance": list(returns.columns),
        "Nom": ["MSCI World ETF", "Government Bond ETF", "Technology ETF"],
        "Secteur": ["ETF", "ETF", "ETF"],
        # Même dtype que les colonnes 1/0/vides de ToutBroker.xlsx.
        "Trading212": pd.Series([1.0, 1.0, np.nan], dtype="float64"),
    })

    selected_returns, selected_frame, diagnostics = select_etfs_per_broker(
        returns, frame, maximum=1
    )

    assert diagnostics["brokers"]["Trading212"]["selected"] == 1
    assert len(selected_returns.columns) == 1
    assert len(selected_frame) == 1


def test_etf_selection_reports_catalog_shortfall(monkeypatch):
    from app.services.finance.buffett import dedup
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import select_etfs_per_broker

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    monkeypatch.setattr(dedup, "returns_in_base_currency", lambda values, _base="EUR": values)
    returns = pd.DataFrame({"ETF1": [0.01] * 80, "ETF2": [0.02] * 80})
    frame = pd.DataFrame({
        "Ticker Yahoo Finance": ["ETF1", "ETF2"],
        "Nom": ["ETF One", "ETF Two"],
        "Secteur": ["ETF", "ETF"],
        "BoursDirect2": [True, True],
    })

    _, _, diagnostics = select_etfs_per_broker(returns, frame, maximum=100)
    broker = diagnostics["brokers"]["BoursDirect2"]

    assert broker["selected"] == 2
    assert broker["shortfall"] == 98
    assert broker["shortfall_reason"] == "eligible_catalog_exhausted"


def test_merge_broker_columns_normalizes_excel_availability(monkeypatch):
    from app.services.finance.buffett import broker_availability
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    excel = pd.DataFrame({
        "Ticker Yahoo Finance": ["AAA", "BBB", "CCC"],
        "Tradding 212": pd.Series([1.0, 0.0, np.nan], dtype="float64"),
    })
    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: excel)
    candidates = pd.DataFrame({"Ticker Yahoo Finance": ["AAA", "BBB", "CCC", "NEW"]})

    merged = broker_availability.merge_broker_columns(candidates)

    assert list(merged["Trading212"][:3]) == [True, False, None]
    assert merged["Trading212"].iloc[3] is None


def test_merge_broker_columns_accepts_an_already_loaded_table(monkeypatch):
    from app.services.finance.buffett import broker_availability
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    monkeypatch.setattr(
        broker_availability,
        "load_broker_table",
        lambda: (_ for _ in ()).throw(AssertionError("le classeur ne doit pas être relu")),
    )
    table = pd.DataFrame({
        "Ticker Yahoo Finance": ["PEA.PA"],
        "Bourse Direct 2": [1.0],
    })
    candidates = pd.DataFrame({"Ticker Yahoo Finance": ["PEA.PA"]})

    merged = broker_availability.merge_broker_columns(
        candidates,
        broker_table=table,
    )

    assert bool(merged["BoursDirect2"].iloc[0]) is True


def test_merge_broker_columns_propagates_secondary_quote_metadata(monkeypatch):
    from app.services.finance.buffett import broker_availability
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    table = pd.DataFrame({
        "Ticker Yahoo Finance": ["WORLD.DE", "WORLD.PA"],
        "Fundamentals Symbol": ["WORLD.DE", "WORLD.DE"],
        "Bourse Direct 2": [False, True],
        "Nom": ["World ETF", "World ETF PEA"],
        "Secteur 1": ["ETF", "ETF"],
        "Secteur 4": [None, "Monde"],
    })

    merged = broker_availability.merge_broker_columns(
        pd.DataFrame({"Ticker Yahoo Finance": ["WORLD.DE"]}),
        broker_table=table,
    )

    assert bool(merged["BoursDirect2"].iloc[0]) is True
    assert merged["Secteur 1"].iloc[0] == "ETF"
    assert merged["Secteur 4"].iloc[0] == "Monde"


def test_merge_broker_columns_ignores_unrelated_catalog_rows(monkeypatch):
    from app.services.finance.buffett import broker_availability
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    table = pd.DataFrame({
        "Ticker Yahoo Finance": ["PRIMARY", "BD.ALIAS", "UNRELATED"],
        "Fundamentals Symbol": ["PRIMARY", "PRIMARY", "OTHER"],
        "Bourse Direct 2": [False, True, True],
        "Secteur 1": ["ETF", "ETF", "ETF"],
        "Secteur 4": [None, "Monde", "Technologie"],
    })

    merged = broker_availability.merge_broker_columns(
        pd.DataFrame({"Ticker Yahoo Finance": ["PRIMARY"]}),
        broker_table=table,
    )

    assert bool(merged["BoursDirect2"].iloc[0]) is True
    assert merged["Secteur 4"].iloc[0] == "Monde"


def test_spearman_correlation_survives_a_stray_false_in_returns():
    """NumPy 2 levait "Invalid value 'False' for dtype 'float64'" quand un
    `False` traînait dans une colonne de rendements (2 runs Buffett en erreur le
    2026-07-20). `to_numeric(errors="coerce")` le neutralise en NaN, puis
    `nan_to_num` le remplace : la matrice reste bien formée et diagonale à 1."""
    from app.services.finance.buffett.etf_selection import _spearman_correlation

    returns = pd.DataFrame({
        "A": np.random.default_rng(0).normal(0, 0.01, 40),
        "B": [False] + list(np.random.default_rng(1).normal(0, 0.01, 39)),
    })

    corr = _spearman_correlation(returns, ["A", "B"])

    assert corr.shape == (2, 2)
    assert np.isfinite(corr).all()
    assert corr[0, 0] == 1.0 and corr[1, 1] == 1.0


def test_excluded_etfs_are_dropped_and_replaced(monkeypatch):
    """Un ETF sans composition Yahoo sort du vivier et libère sa place.

    Le runner rejoue la présélection avec `excluded_tickers` : l'ETF écarté doit
    disparaître des rendements ET du tableau (il ne doit pas se faufiler par la
    branche « non-ETF » du filtre final), et un remplaçant doit être choisi.
    """
    from app.services.finance.buffett import dedup
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.etf_selection import select_etfs_per_broker

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"A": 1000.0})
    monkeypatch.setattr(Config, "ETF_SELECTION_CORRELATION_DAYS", 100)
    monkeypatch.setattr(dedup, "returns_in_base_currency", lambda values, _base="EUR": values)

    etfs = ["WORLD", "USA", "EUROPE", "GOLD", "BONDS"]
    rng = np.random.default_rng(3)
    common = rng.normal(0, 0.01, 160)
    returns = pd.DataFrame({
        "WORLD": common + rng.normal(0, 0.001, 160),
        "USA": common + rng.normal(0, 0.001, 160),
        "EUROPE": 0.7 * common + rng.normal(0, 0.004, 160),
        "GOLD": -0.2 * common + rng.normal(0, 0.007, 160),
        "BONDS": -0.1 * common + rng.normal(0, 0.003, 160),
        "NVDA": common + rng.normal(0, 0.012, 160),
    })
    names = {
        "WORLD": "MSCI World ETF",
        "USA": "S&P 500 ETF",
        "EUROPE": "Europe ETF",
        "GOLD": "Physical Gold ETF",
        "BONDS": "Government Bond ETF",
    }
    rows = [
        {
            "Ticker Yahoo Finance": ticker,
            "Nom": names[ticker],
            "Secteur": "ETF",
            "Volume": 1000,
            "Poids": 0.0,
            "A": True,
        }
        for ticker in etfs
    ]
    rows.append({
        "Ticker Yahoo Finance": "NVDA",
        "Nom": "NVDA",
        "Secteur": "Technology",
        "Volume": 5000,
        "Poids": 0.0,
        "A": True,
    })
    frame = pd.DataFrame(rows)

    _, _, before = select_etfs_per_broker(returns, frame, maximum=3)
    retained = set(before["brokers"]["A"]["selected_tickers"])
    dropped = sorted(retained)[0]

    kept_returns, kept_frame, after = select_etfs_per_broker(
        returns, frame, maximum=3, excluded_tickers={dropped}
    )

    assert dropped not in kept_returns.columns
    assert dropped not in set(kept_frame["Ticker Yahoo Finance"])
    assert after["excluded"] == [dropped]
    # La place libérée est reprise par un autre ETF, pas perdue.
    assert after["brokers"]["A"]["selected"] == before["brokers"]["A"]["selected"]
    # Les actions ne sont jamais touchées par l'exclusion d'un ETF.
    assert "NVDA" in kept_returns.columns
