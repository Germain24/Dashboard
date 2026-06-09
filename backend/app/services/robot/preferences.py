"""Préférences Robot réglables (#161) : modèle, effort, max_tokens.

Persistées dans un JSON local (data/robot_prefs.json), override des valeurs
.env. La température n'est PAS exposée : Claude Opus 4.8 ne l'accepte plus
(le paramètre est retiré) ; on règle l'intensité via `effort`.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings

VALID_EFFORTS = ("low", "medium", "high", "max")


def prefs_file() -> Path:
    return settings.data_dir / "robot_prefs.json"


def get_prefs(*, path: Path | None = None) -> dict:
    p = path or prefs_file()
    base = {
        "model": settings.robot_model,
        "effort": settings.robot_effort,
        "max_tokens": settings.robot_max_tokens,
    }
    if p.exists():
        try:
            base.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                         if k in base})
        except (json.JSONDecodeError, OSError):
            pass
    return base


def set_prefs(model: str | None = None, effort: str | None = None,
              max_tokens: int | None = None, *, path: Path | None = None) -> dict:
    prefs = get_prefs(path=path)
    if model:
        prefs["model"] = model
    if effort:
        if effort not in VALID_EFFORTS:
            raise ValueError(f"effort invalide : {effort}")
        prefs["effort"] = effort
    if max_tokens is not None:
        if max_tokens < 256:
            raise ValueError("max_tokens trop bas (min 256)")
        prefs["max_tokens"] = int(max_tokens)
    p = path or prefs_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    return prefs
