"""yf.download(..., group_by="ticker") renvoie des colonnes MultiIndex
(Ticker, Price) MÊME avec un seul ticker (yfinance>=0.2.28+) — le code qui
suppose des colonnes aplaties pour 1 ticker (raw["Close"]) lève
KeyError: 'Close'. Reproduit ici la forme réelle du DataFrame yfinance."""

import pandas as pd
import pytest


def _fake_download(tickers: list[str]) -> pd.DataFrame:
    """Mime yf.download(tickers, group_by="ticker") : MultiIndex (Ticker, Price)."""
    idx = pd.date_range("2026-01-01", periods=3)
    cols = pd.MultiIndex.from_product([tickers, ["Open", "High", "Low", "Close", "Volume"]])
    data = {}
    for i, t in enumerate(tickers):
        for j, field in enumerate(["Open", "High", "Low", "Close", "Volume"]):
            data[(t, field)] = [100.0 + i + j + k for k in range(3)]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_single_ticker_multiindex_download():
    """Un seul ticker : yfinance renvoie quand même un MultiIndex (Ticker, Price)."""
    from app.services.finance.buffett.allocation import close_prices_from_download

    raw = _fake_download(["AAPL"])
    cd = close_prices_from_download(raw, ["AAPL"])
    assert list(cd.columns) == ["AAPL"]
    assert len(cd) == 3
    assert cd["AAPL"].iloc[0] == pytest.approx(103.0)  # Open+High+Low(idx2)+Close... voir calcul


def test_multi_ticker_multiindex_download():
    from app.services.finance.buffett.allocation import close_prices_from_download

    raw = _fake_download(["AAPL", "MSFT"])
    cd = close_prices_from_download(raw, ["AAPL", "MSFT"])
    assert sorted(cd.columns) == ["AAPL", "MSFT"]
    assert len(cd) == 3


def test_missing_ticker_dropped_not_raised():
    """Un ticker demandé mais absent du téléchargement (échec yfinance) est
    simplement ignoré, pas une KeyError."""
    from app.services.finance.buffett.allocation import close_prices_from_download

    raw = _fake_download(["AAPL"])
    cd = close_prices_from_download(raw, ["AAPL", "GHOST"])
    assert list(cd.columns) == ["AAPL"]
