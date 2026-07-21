"""Cache non bloquant des benchmarks affichés dans l'interface Finance."""

from __future__ import annotations

import threading

from app.services.finance import benchmarks


def _metric(value: float) -> dict:
    return {
        "perf_1y_pct": value,
        "perf_6m_pct": value / 2,
        "perf_mtd_pct": value / 10,
        "serie": [{"date": "2026-07-15", "valeur": 100.0}],
    }


def test_background_benchmark_refresh_does_not_block_first_response(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(benchmarks, "_CACHE_FILE", tmp_path / "benchmarks.json")
    monkeypatch.setattr(benchmarks, "_analysis_running", lambda: False)
    benchmarks.clear_cache()
    started = threading.Event()
    release = threading.Event()
    saved = threading.Event()

    def slow_fetch(ticker):
        started.set()
        assert release.wait(2)
        return _metric(8.0)

    original_save = benchmarks._save_disk_cache

    def save_and_signal():
        original_save()
        saved.set()

    monkeypatch.setattr(benchmarks, "_fetch_perf", slow_fetch)
    monkeypatch.setattr(benchmarks, "_save_disk_cache", save_and_signal)

    first = benchmarks.get_benchmarks(background_refresh=True)
    assert first == {"CW8": None, "SP500": None, "MSCI_WORLD": None}
    assert started.wait(1)

    release.set()
    assert saved.wait(2)
    second = benchmarks.get_benchmarks(background_refresh=True)
    assert all(second[name] is not None for name in benchmarks.BENCHMARKS)
    benchmarks.clear_cache()


def test_cw8_simulation_is_built_in_background(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmarks, "_CACHE_FILE", tmp_path / "benchmarks.json")
    monkeypatch.setattr(benchmarks, "_analysis_running", lambda: False)
    benchmarks.clear_cache()
    started = threading.Event()
    release = threading.Event()
    stored = threading.Event()
    simulation = [
        {"date": "2026-07-14", "valeur": 1000.0},
        {"date": "2026-07-15", "valeur": 1010.0},
    ]

    monkeypatch.setattr(
        benchmarks,
        "get_benchmarks",
        lambda *, background_refresh=False: {
            "CW8": _metric(8.0),
            "SP500": None,
            "MSCI_WORLD": None,
        },
    )

    def slow_simulation(_snapshots, _ticker):
        started.set()
        assert release.wait(2)
        return simulation

    original_store = benchmarks._store_simulation

    def store_and_signal(*args, **kwargs):
        original_store(*args, **kwargs)
        stored.set()

    monkeypatch.setattr(benchmarks, "simulate_benchmark_dca", slow_simulation)
    monkeypatch.setattr(benchmarks, "_store_simulation", store_and_signal)
    snapshots = [
        {"date": "2026-07-14", "valeur": 1000.0, "investit": 1000.0},
        {"date": "2026-07-15", "valeur": 1020.0, "investit": 1000.0},
    ]

    first = benchmarks.get_portfolio_vs_benchmarks(
        snapshots, background_refresh=True
    )
    assert first["benchmarks"]["CW8"]["serie"] == []
    assert started.wait(1)

    release.set()
    assert stored.wait(2)
    second = benchmarks.get_portfolio_vs_benchmarks(
        snapshots, background_refresh=True
    )
    assert second["benchmarks"]["CW8"]["serie"] == simulation
    benchmarks.clear_cache()
