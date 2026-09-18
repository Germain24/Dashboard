"""Rappel mensuel de mise à jour du score de crédit (#credit-reminder).

Un job périodique (~5 du mois, cf. `app.services.scheduler.jobs.credit_reminders`)
vérifie qu'aucun rappel n'a encore été envoyé ce mois-ci et crée une
Notification. Un store JSON évite les doublons dans le même mois — même
logique que `app.services.habitudes.reminders` / `app.services.agenda.reminders`,
mais à la granularité mensuelle plutôt que journalière.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

from app.core.config import settings


def reminded_file() -> Path:
    return settings.data_dir / "credit_score_reminded.json"


def _read_reminded(*, path: Optional[Path] = None) -> set[str]:
    p = path or reminded_file()
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data) if isinstance(data, list) else set()


def _write_reminded(keys: set[str], *, path: Optional[Path] = None) -> None:
    p = path or reminded_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(keys)[-24:], ensure_ascii=False), encoding="utf-8")


def reminder_key(date: dt.date) -> str:
    """Clé mensuelle (ex: '2026-07') — un seul rappel par mois."""
    return f"{date.year:04d}-{date.month:02d}"


def should_remind(date: dt.date, *, path: Optional[Path] = None) -> bool:
    """Pur : retourne True si aucun rappel n'a encore été envoyé ce mois-ci."""
    return reminder_key(date) not in _read_reminded(path=path)


def mark_reminded(date: dt.date, *, path: Optional[Path] = None) -> None:
    reminded = _read_reminded(path=path)
    reminded.add(reminder_key(date))
    _write_reminded(reminded, path=path)
