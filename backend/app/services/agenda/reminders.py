"""Rappels d'événements → notifications (#85).

Un job périodique (cf. scheduler.jobs.agenda_reminders) appelle `due_events`
pour repérer les événements qui débutent dans la fenêtre à venir, puis crée une
`Notification` pour chacun. Un petit store JSON (`data/agenda_reminded.json`)
évite d'envoyer deux fois le même rappel.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings

DEFAULT_LOOKAHEAD_MIN = 30


def reminded_file() -> Path:
    return settings.data_dir / "agenda_reminded.json"


def reminder_key(titre: str, debut: dt.datetime) -> str:
    return f"{debut.strftime('%Y-%m-%dT%H:%M')}|{titre}"


def format_reminder(
    debut: dt.datetime, now: dt.datetime, lieu: Optional[str] = None
) -> str:
    """Message de rappel contextuel (#214) : temps relatif + heure + lieu si dispo.

    Ex. « dans 25 min · 14:30 · Local B-2045 ». Plus actionnable qu'un simple
    « À 14:30 » : on sait *dans combien de temps* et *où*.
    """
    mins = round((debut - now).total_seconds() / 60)
    quand = "maintenant" if mins <= 0 else f"dans {mins} min"
    msg = f"{quand} · {debut.strftime('%H:%M')}"
    if lieu:
        msg += f" · {lieu}"
    return msg


def due_events(
    events: list[dict[str, Any]],
    now: dt.datetime,
    lookahead_min: int = DEFAULT_LOOKAHEAD_MIN,
) -> list[dict[str, Any]]:
    """Événements dont le début tombe dans (now, now + lookahead]."""
    horizon = now + dt.timedelta(minutes=lookahead_min)
    out = []
    for e in events:
        debut = e.get("debut")
        if isinstance(debut, dt.datetime) and now < debut <= horizon:
            out.append(e)
    return out


def load_reminded(*, path: Optional[Path] = None) -> set[str]:
    p = path or reminded_file()
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data) if isinstance(data, list) else set()


def save_reminded(keys: set[str], *, path: Optional[Path] = None, keep: int = 500) -> None:
    """Persiste les clés déjà notifiées (tronquées aux `keep` plus récentes)."""
    p = path or reminded_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    # tri lexicographique = chronologique (clé préfixée par l'ISO datetime)
    trimmed = sorted(keys)[-keep:]
    p.write_text(json.dumps(trimmed, ensure_ascii=False), encoding="utf-8")
