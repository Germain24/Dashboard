"""Persistance progressive et atomique du cache Buffett."""

from __future__ import annotations

import json

import pytest

from app.services.finance.buffett import cache_manager as cache_module
from app.services.finance.buffett import runner
from app.services.finance.buffett.cache_manager import CacheManager


def test_save_if_dirty_writes_once_and_creates_valid_json(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = CacheManager(str(cache_path))
    cache.update("AAPL", 2025, 81.0, {"VolumeDevise": "EUR"})

    assert cache.save_if_dirty() is True
    assert cache.save_if_dirty() is False
    assert json.loads(cache_path.read_text(encoding="utf-8"))["AAPL"]["score"] == 81.0
    assert list(tmp_path.glob(".cache.json.*.tmp")) == []


def test_failed_atomic_replace_keeps_previous_cache_and_remains_retryable(
    tmp_path,
    monkeypatch,
):
    cache_path = tmp_path / "cache.json"
    cache = CacheManager(str(cache_path))
    cache.update("AAPL", 2025, 81.0, {"Achat": False})
    cache.save()

    cache.update("AAPL", 2025, 82.0, {"Achat": True})
    real_replace = cache_module.os.replace

    def fail_replace(source, destination):
        raise OSError("simulated interruption before atomic replace")

    monkeypatch.setattr(cache_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        cache.save_if_dirty()

    # L'ancien fichier reste lisible et aucun temporaire orphelin ne subsiste.
    on_disk = json.loads(cache_path.read_text(encoding="utf-8"))
    assert on_disk["AAPL"]["score"] == 81.0
    assert list(tmp_path.glob(".cache.json.*.tmp")) == []

    # L'état dirty n'est acquitté qu'après un remplacement réellement réussi.
    monkeypatch.setattr(cache_module.os, "replace", real_replace)
    assert cache.save_if_dirty() is True
    assert json.loads(cache_path.read_text(encoding="utf-8"))["AAPL"]["score"] == 82.0


def test_progressive_checkpoint_is_due_by_count_or_elapsed_time():
    assert not runner._cache_checkpoint_due(
        runner.CACHE_CHECKPOINT_EVERY_RESULTS - 1,
        runner.CACHE_CHECKPOINT_INTERVAL_S - 0.001,
    )
    assert runner._cache_checkpoint_due(runner.CACHE_CHECKPOINT_EVERY_RESULTS, 0.0)
    assert runner._cache_checkpoint_due(0, runner.CACHE_CHECKPOINT_INTERVAL_S)


def test_checkpoint_failure_is_non_fatal_and_retryable(capsys):
    class FailingCache:
        def save_if_dirty(self):
            raise OSError("disk unavailable")

    assert runner._persist_cache_checkpoint(FailingCache(), "test") is False
    assert "disk unavailable" in capsys.readouterr().out
