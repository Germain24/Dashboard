import numpy as np
import pandas as pd


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
