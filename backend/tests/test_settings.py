"""Tests settings store (#544)."""

import json
import pytest
from pathlib import Path

from app.services.settings import (
    SettingsStore,
    get_preferences,
    set_preferences,
    DEFAULT_PREFS,
)


@pytest.fixture
def store(tmp_path):
    return SettingsStore(tmp_path / "settings.json")


def test_default_prefs_returned_when_file_absent(store):
    prefs = store.load()
    assert "backup_retention_count" in prefs
    assert prefs["backup_retention_count"] == DEFAULT_PREFS["backup_retention_count"]


def test_save_and_reload(store):
    store.save({"backup_retention_count": 30})
    prefs = store.load()
    assert prefs["backup_retention_count"] == 30


def test_partial_update_merges(store):
    store.save({"backup_retention_count": 7})
    store.update({"jobrun_retention_days": 60})
    prefs = store.load()
    assert prefs["backup_retention_count"] == 7
    assert prefs["jobrun_retention_days"] == 60


def test_defaults_filled_on_partial_file(store):
    store._path.write_text(json.dumps({"backup_retention_count": 5}))
    prefs = store.load()
    # Les clés absentes du fichier sont complétées par les defaults
    assert "jobrun_retention_days" in prefs
    assert prefs["backup_retention_count"] == 5


def test_only_known_keys_saved(store):
    store.save({"backup_retention_count": 10, "hacker_key": "bad"})
    prefs = store.load()
    assert "hacker_key" not in prefs
    assert prefs["backup_retention_count"] == 10
