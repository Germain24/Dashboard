"""ETF déterminés par la colonne 'Secteur 1' de ToutBroker.xlsx (== 'ETF')."""

import pandas as pd


def _df():
    return pd.DataFrame({
        "Ticker Yahoo Finance": ["CW8.PA", "AAPL", "BA.TO", "SEGA.L"],
        "Nom": ["Amundi MSCI World", "Apple Inc.", "The Boeing Company", "iShares Govt Bond"],
        "Secteur 1": ["ETF", "Technology", None, "etf"],  # casse + valeur vide gérées
    })


def test_load_etf_tickers_from_secteur1():
    from app.services.finance.buffett.broker_availability import load_etf_tickers
    etf = load_etf_tickers(df=_df())
    assert etf == {"CW8.PA", "SEGA.L"}   # 'ETF' et 'etf', pas Apple ni Boeing(None)


def test_load_broker_universe_all_tickers():
    from app.services.finance.buffett.broker_availability import load_broker_universe
    uni = load_broker_universe(df=_df())
    assert uni == {"CW8.PA", "AAPL", "BA.TO", "SEGA.L"}


def test_load_etf_tickers_empty_when_no_secteur1_column():
    from app.services.finance.buffett.broker_availability import load_etf_tickers
    df = pd.DataFrame({"Ticker Yahoo Finance": ["X"], "Nom": ["Y"]})
    assert load_etf_tickers(df=df) == set()
