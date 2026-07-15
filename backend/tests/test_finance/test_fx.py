"""Taux de change avec cache quotidien."""

from __future__ import annotations

import datetime as dt

from app.services.finance import fx


def test_same_currency_is_one():
    assert fx.get_rate("EUR", "EUR") == 1.0


def test_rate_cached_same_day():
    fx.clear_cache()
    calls = []

    def fake(b, q):
        calls.append((b, q))
        return 1.1 if (b, q) == ("EUR", "USD") else None

    day = dt.date(2026, 6, 3)
    assert fx.get_rate("EUR", "USD", fetcher=fake, today=day) == 1.1
    assert fx.get_rate("EUR", "USD", fetcher=fake, today=day) == 1.1
    assert len(calls) == 1  # un seul appel le même jour


def test_convert():
    fx.clear_cache()
    r = fx.convert(100.0, "EUR", "USD", fetcher=lambda b, q: 1.1, today=dt.date(2026, 6, 3))
    assert r == 110.0


def test_fallback_inverse():
    fx.clear_cache()

    def fake(b, q):
        # seul USD->EUR connu = 0.5 ; EUR->USD doit être déduit = 2.0
        return 0.5 if (b, q) == ("USD", "EUR") else None

    r = fx.get_rate("EUR", "USD", fetcher=fake, today=dt.date(2026, 6, 3))
    assert r == 2.0


# ── Cache NEGATIF : une paire dont le fetch echoue ne doit pas etre re-tentee
# a chaque appel (meme probleme que prices.py : famine du throttle global). ──

def test_failed_pair_not_refetched_within_retry_window(monkeypatch):
    fx.clear_cache()
    calls = []

    def failing(b, q):
        calls.append((b, q))
        return None

    day = dt.date(2026, 6, 3)
    monkeypatch.setattr(fx, "_now", lambda: 1000.0)
    assert fx.get_rate("EUR", "XXX", fetcher=failing, today=day) == 0.0
    monkeypatch.setattr(fx, "_now", lambda: 1000.0 + 600.0)
    assert fx.get_rate("EUR", "XXX", fetcher=failing, today=day) == 0.0

    assert calls == [("EUR", "XXX"), ("XXX", "EUR")]  # 1 tentative (+ inverse), pas 2


def test_failed_pair_refetched_after_retry_window(monkeypatch):
    fx.clear_cache()
    calls = []

    def fetch(b, q):
        calls.append((b, q))
        # Echec des 2 premieres tentatives (directe + inverse), succes ensuite
        return 1.1 if len(calls) > 2 else None

    day = dt.date(2026, 6, 3)
    monkeypatch.setattr(fx, "_now", lambda: 1000.0)
    fx.get_rate("EUR", "USD", fetcher=fetch, today=day)
    monkeypatch.setattr(fx, "_now", lambda: 1000.0 + fx.NEG_RETRY_S + 1.0)
    assert fx.get_rate("EUR", "USD", fetcher=fetch, today=day) == 1.1


def test_no_fetch_while_analysis_running(monkeypatch):
    fx.clear_cache()
    calls = []
    monkeypatch.setattr(fx, "_analysis_running", lambda: True)
    r = fx.get_rate("EUR", "USD", fetcher=lambda b, q: calls.append((b, q)) or 1.1,
                    today=dt.date(2026, 6, 3))
    assert calls == []
    assert r == 0.0


def test_serves_stale_rate_while_analysis_running(monkeypatch):
    fx.clear_cache()
    monkeypatch.setattr(fx, "_analysis_running", lambda: False)
    fx.get_rate("EUR", "USD", fetcher=lambda b, q: 1.1, today=dt.date(2026, 6, 3))
    monkeypatch.setattr(fx, "_analysis_running", lambda: True)
    r = fx.get_rate("EUR", "USD", fetcher=lambda b, q: 9.9, today=dt.date(2026, 6, 4))
    assert r == 1.1  # dernier taux connu, pas de fetch live


def test_get_rate_force_contourne_le_garde_analyse(monkeypatch):
    """Pendant une analyse, get_rate ne fetch jamais (garde _analysis_running)
    -> le warm-up doit pouvoir forcer le fetch, sinon toute paire jamais vue
    ce jour vaudrait 0 pendant tout le run."""
    from app.services.finance import fx
    fx.clear_cache()
    monkeypatch.setattr(fx, "_analysis_running", lambda: True)
    calls = []

    def fetch(base, quote):
        calls.append((base, quote))
        return 1.25

    assert fx.get_rate("USD", "EUR", fetcher=fetch) == 0.0      # garde actif
    assert calls == []
    assert fx.get_rate("USD", "EUR", fetcher=fetch, force=True) == 1.25
    assert calls == [("USD", "EUR")]
    # Le taux forcé est en cache : l'appel normal suivant le voit.
    assert fx.get_rate("USD", "EUR", fetcher=fetch) == 1.25
    assert calls == [("USD", "EUR")]
    fx.clear_cache()
