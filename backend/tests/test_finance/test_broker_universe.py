"""Univers achetable (ToutBroker.xlsx) servant à restreindre l'analyse Buffett."""

from __future__ import annotations

from app.services.finance.buffett.broker_availability import broker_available_tickers


def test_broker_universe_is_normalised_and_bounded():
    univ = broker_available_tickers()
    assert isinstance(univ, set)
    if univ:  # fichier ToutBroker.xlsx présent
        assert all(t == t.upper() and t.strip() == t for t in univ)
        # l'intérêt même de la fonction : bien plus petit que tickers.csv (~65k)
        assert len(univ) < 20000
