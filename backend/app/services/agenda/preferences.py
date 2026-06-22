"""Préférences de planification (page Préférences, remplace l'onglet Tâches).

Pour l'instant : moment préféré par activité (matin/aprem/soir) — consommé par
le planificateur unique (`plan_cycle` via `auto_plan`). Stocké en JSON
(data/agenda_preferences.json), pas de migration. Extensible (jours préférés,
ordre d'importance) plus tard.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings

ACTIVITIES = ("sport", "etudes", "cuisine")
MOMENTS = ("matin", "aprem", "soir")


def _path() -> Path:
    return settings.data_dir / "agenda_preferences.json"


def get_preferences() -> dict:
    """Préférences validées : {"moments": {activité: moment}}."""
    p = _path()
    if not p.exists():
        return {"moments": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        moments = {
            k: v for k, v in (data.get("moments") or {}).items()
            if k in ACTIVITIES and v in MOMENTS
        }
        return {"moments": moments}
    except Exception:
        return {"moments": {}}


def set_preferences(patch: dict) -> dict:
    """Met à jour les moments. `v` vide/None retire la préférence. Retourne l'état."""
    moments = dict(get_preferences()["moments"])
    for k, v in (patch.get("moments") or {}).items():
        if k not in ACTIVITIES:
            continue
        if v in MOMENTS:
            moments[k] = v
        elif v in (None, ""):
            moments.pop(k, None)
    out = {"moments": moments}
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
