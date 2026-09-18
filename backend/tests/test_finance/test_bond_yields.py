"""Tests TDD — rafraîchissement automatique des taux obligataires (Buffett)."""

from __future__ import annotations

import datetime as dt

from app.services.finance.buffett import bond_yields as by


def test_normalize_percent_to_fraction():
    assert by._normalize_yield(4.23) == 0.0423   # Yahoo cote en %
    assert by._normalize_yield(0.7) == 0.007


def test_normalize_rejects_absurd_or_missing():
    assert by._normalize_yield(None) is None
    assert by._normalize_yield(0) is None
    assert by._normalize_yield(-1) is None
    assert by._normalize_yield(42.0) is None     # ^TNX ×10 → hors plage → repli


def test_parse_fred_csv_takes_last_numeric_value():
    csv = "observation_date,DGS10\n2026-06-12,4.41\n2026-06-15,4.47\n"
    assert by._parse_fred_csv(csv) == 4.47


def test_parse_fred_csv_skips_missing_dots():
    csv = "DATE,VAL\n2026-05-01,3.50\n2026-06-01,.\n"  # « . » = donnée manquante FRED
    assert by._parse_fred_csv(csv) == 3.50


def test_parse_fred_csv_empty():
    assert by._parse_fred_csv("observation_date,DGS10\n") is None


def test_merge_overrides_defaults_with_live():
    out = by.merge_yields({"United States": 4.5}, {"United States": 0.042, "France": 0.029})
    assert out["United States"] == 0.045         # live
    assert out["France"] == 0.029                # repli conservé


def test_merge_ignores_invalid_live_keeps_default():
    out = by.merge_yields({"United States": None, "France": 999.0}, {"United States": 0.042, "France": 0.029})
    assert out["United States"] == 0.042
    assert out["France"] == 0.029


def test_get_bond_yields_uses_injected_fetcher_and_caches():
    calls = {"n": 0}

    def fake_fetch(tickers):
        calls["n"] += 1
        return {"United States": 4.10}

    today = dt.date(2026, 6, 17)
    out1 = by.get_bond_yields(fetcher=fake_fetch, today=today, force=True)
    assert out1["United States"] == 0.041
    # deuxième appel le même jour → cache, pas de nouvel appel réseau
    out2 = by.get_bond_yields(fetcher=fake_fetch, today=today)
    assert calls["n"] == 1
    assert out2["United States"] == 0.041


def test_get_bond_yields_refreshes_full_g7():
    # Fetcher simulant FRED pour le G7 (valeurs en %).
    def fake_fetch(series_map):
        pct = {"United States": 4.47, "Canada": 3.54, "France": 3.74, "Germany": 3.05,
               "Italy": 3.82, "Japan": 2.65, "United Kingdom": 4.94}
        return {pays: pct.get(pays) for pays in series_map}

    out = by.get_bond_yields(fetcher=fake_fetch, today=dt.date(2026, 6, 18), force=True)
    assert out["United States"] == 0.0447
    assert out["Italy"] == 0.0382
    assert out["United Kingdom"] == 0.0494
    assert out["Switzerland"] == 0.007   # hors G7 → repli statique conservé


def test_fetched_countries_have_static_fallback():
    # Tout pays fetché doit avoir un repli statique (sinon trou si réseau KO).
    for pays in by.SERIES_BY_COUNTRY:
        assert pays in by.STATIC_BOND_YIELDS


def test_series_cover_g7_plus_more():
    g7 = {"United States", "Canada", "France", "Germany", "Italy", "Japan", "United Kingdom"}
    assert g7 <= set(by.SERIES_BY_COUNTRY)
    assert len(by.SERIES_BY_COUNTRY) >= 18   # G7 + OCDE supplémentaires


def test_get_bond_yields_falls_back_when_fetch_fails():
    def boom(tickers):
        raise RuntimeError("réseau indisponible")

    out = by.get_bond_yields(
        fetcher=boom, defaults={"United States": 0.042}, today=dt.date(2026, 1, 1), force=True,
    )
    assert out == {"United States": 0.042}       # repli, jamais pire que les constantes
