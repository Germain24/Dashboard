"""Test de non-régression : fast_last_price contourne le bug FastInfo.get() (yfinance 1.x).

Dans yfinance 1.x, `FastInfo.get("last_price")` renvoie toujours le défaut
(None) → tous les cours tombaient à 0 (CW8.PA, etc.). fast_last_price accède par
clé et retombe sur l'historique.
"""

import pandas as pd

from app.services.finance.yf_session import fast_last_price


class _FastInfoBug:
    """Simule FastInfo : l'accès par clé marche, mais .get() est cassé."""

    def __init__(self, price):
        self._price = price

    def __getitem__(self, key):
        if key == "last_price":
            return self._price
        raise KeyError(key)

    def get(self, _key, default=None):
        return default  # bug yfinance : ignore la vraie valeur


class _FastInfoBugWithCurrency(_FastInfoBug):
    """Comme _FastInfoBug, mais expose aussi `currency` (bug .get() inclus)."""

    def __init__(self, price, currency):
        super().__init__(price)
        self._currency = currency

    def __getitem__(self, key):
        if key == "currency":
            return self._currency
        return super().__getitem__(key)


class _Ticker:
    def __init__(self, price=None, hist_close=None, currency=None):
        self.fast_info = (
            _FastInfoBugWithCurrency(price, currency) if currency is not None
            else _FastInfoBug(price)
        )
        self._hist_close = hist_close

    def history(self, period="5d"):
        if self._hist_close is None:
            return pd.DataFrame()
        return pd.DataFrame({"Close": self._hist_close})


def test_uses_key_access_not_broken_get():
    assert fast_last_price(_Ticker(price=668.40)) == 668.40


def test_falls_back_to_history_when_no_last_price():
    t = _Ticker(price=None, hist_close=[100.0, 101.5, 667.14])
    assert fast_last_price(t) == 667.14


def test_zero_when_nothing_available():
    assert fast_last_price(_Ticker(price=None, hist_close=None)) == 0.0


def test_get_would_have_returned_none():
    # Confirme que le bug existe : .get() renvoie bien None (≠ valeur réelle).
    assert _Ticker(price=668.40).fast_info.get("last_price") is None


def test_lse_pence_quoted_ticker_divided_by_100():
    """Titre londonien coté en pence (currency="GBp") -- ex. un ETC or à
    5929 (pence) doit remonter comme 59.29 (livres), pas 5929 (#bug SGLN.L)."""
    assert fast_last_price(_Ticker(price=5929.0, currency="GBp")) == 59.29


def test_gbx_currency_code_also_treated_as_pence():
    assert fast_last_price(_Ticker(price=100.0, currency="GBX")) == 1.0


def test_gbp_currency_not_divided():
    assert fast_last_price(_Ticker(price=42.5, currency="GBP")) == 42.5


def test_pence_division_also_applies_to_history_fallback():
    t = _Ticker(price=None, hist_close=[5000.0, 5929.0], currency="GBp")
    assert fast_last_price(t) == 59.29
