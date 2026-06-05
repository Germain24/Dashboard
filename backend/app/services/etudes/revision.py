"""Révision espacée (spaced repetition) sur fiches — SM-2 simplifié (#99).

Chaque fiche (recto/verso, liée à un cours optionnel) a un état SM-2 :
ease (facilité), interval (jours), reps (répétitions réussies), due (date due).
À chaque révision, l'utilisateur note la qualité de rappel (0-5) ; le planning
de la prochaine révision est recalculé.

Stockage JSON local (`data/etudes_revision.json`), sans migration.
`schedule` est pur et testable.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

EASE_MIN = 1.3
EASE_DEFAULT = 2.5


def schedule(reps: int, ease: float, interval: int, quality: int) -> dict[str, Any]:
    """Applique SM-2 simplifié. `quality` 0-5 (>=3 = rappel réussi)."""
    q = max(0, min(5, int(quality)))
    if q < 3:
        # Échec : on repart à zéro (révision le lendemain).
        return {"reps": 0, "ease": max(EASE_MIN, ease), "interval": 1}

    if reps == 0:
        new_interval = 1
    elif reps == 1:
        new_interval = 6
    else:
        new_interval = round(interval * ease)

    new_ease = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ease = max(EASE_MIN, round(new_ease, 2))
    return {"reps": reps + 1, "ease": new_ease, "interval": max(1, new_interval)}


def revision_file() -> Path:
    from app.core.config import settings
    return settings.data_dir / "etudes_revision.json"


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(path: Path, cards: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")


def list_cards(*, path: Optional[Path] = None) -> list[dict[str, Any]]:
    return _read(path or revision_file())


def add_card(
    recto: str,
    verso: str,
    cours_id: Optional[int] = None,
    *,
    path: Optional[Path] = None,
    today: Optional[dt.date] = None,
) -> dict[str, Any]:
    if not recto.strip() or not verso.strip():
        raise ValueError("Recto et verso requis")
    today = today or dt.date.today()
    p = path or revision_file()
    cards = _read(p)
    new_id = (max((c.get("id", 0) for c in cards), default=0) + 1)
    card = {
        "id": new_id,
        "cours_id": cours_id,
        "recto": recto.strip(),
        "verso": verso.strip(),
        "ease": EASE_DEFAULT,
        "interval": 0,
        "reps": 0,
        "due": today.isoformat(),
    }
    cards.append(card)
    _write(p, cards)
    return card


def review_card(card_id: int, quality: int, *, path: Optional[Path] = None, today: Optional[dt.date] = None) -> dict[str, Any]:
    today = today or dt.date.today()
    p = path or revision_file()
    cards = _read(p)
    for c in cards:
        if c.get("id") == card_id:
            res = schedule(int(c.get("reps", 0)), float(c.get("ease", EASE_DEFAULT)), int(c.get("interval", 0)), quality)
            c.update(res)
            c["due"] = (today + dt.timedelta(days=res["interval"])).isoformat()
            _write(p, cards)
            return c
    raise KeyError(card_id)


def delete_card(card_id: int, *, path: Optional[Path] = None) -> bool:
    p = path or revision_file()
    cards = _read(p)
    new = [c for c in cards if c.get("id") != card_id]
    if len(new) == len(cards):
        return False
    _write(p, new)
    return True


def due_cards(*, path: Optional[Path] = None, today: Optional[dt.date] = None) -> list[dict[str, Any]]:
    """Fiches à réviser aujourd'hui (due <= today)."""
    today = today or dt.date.today()
    out = []
    for c in _read(path or revision_file()):
        try:
            due = dt.date.fromisoformat(c.get("due", today.isoformat()))
        except ValueError:
            due = today
        if due <= today:
            out.append(c)
    return out
