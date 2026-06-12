"""Store de préférences applicatives (#544).

Les secrets (clés API) restent dans .env ; cette couche gère les préférences
éditables depuis la page /parametres (rétentions, dossier musique, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings as env_settings

DEFAULT_PREFS: dict = {
    "backup_retention_count": 14,
    "jobrun_retention_days": 30,
    "notification_retention_days": 30,
    "music_dir": "C:/Users/germa/Music",
}

_ALLOWED_KEYS = set(DEFAULT_PREFS.keys())


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self._path = path or (env_settings.data_dir / "app_settings.json")

    def load(self) -> dict:
        prefs = dict(DEFAULT_PREFS)
        if self._path.exists():
            try:
                saved = json.loads(self._path.read_text(encoding="utf-8"))
                for k in _ALLOWED_KEYS:
                    if k in saved:
                        prefs[k] = saved[k]
            except Exception:
                pass
        return prefs

    def save(self, data: dict) -> dict:
        clean = {k: v for k, v in data.items() if k in _ALLOWED_KEYS}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.load()

    def update(self, patch: dict) -> dict:
        current = self.load()
        for k, v in patch.items():
            if k in _ALLOWED_KEYS:
                current[k] = v
        return self.save(current)


_store = SettingsStore()


def get_preferences() -> dict:
    return _store.load()


def set_preferences(patch: dict) -> dict:
    return _store.update(patch)
