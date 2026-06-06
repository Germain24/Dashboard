"""Programme périodisé (mésocycle) avec progression auto — #110.

Schéma hypertrophie : le volume hebdomadaire (séries) monte de MEV vers MRV
semaine après semaine pendant `accumulation_weeks` semaines, puis une semaine de
deload (volume réduit). La semaine courante se déduit du calendrier (avance auto).
Overlay non destructif : on ne réécrit jamais le programme stocké ; on calcule la
cible de la semaine à la volée. Store JSON local, sans migration.

`current_phase` et `adjust_sets` sont purs et testables (date injectable).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings as _settings

DEFAULT_ACCUMULATION_WEEKS = _settings.entrainement_mesocycle_accumulation_weeks


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def current_phase(start_date: dt.date, accumulation_weeks: int, today: dt.date) -> dict[str, Any]:
    """Phase/semaine courante du mésocycle, déduite du calendrier (ancrage lundi)."""
    weeks_elapsed = max(0, (_monday(today) - _monday(start_date)).days // 7)
    cycle_len = accumulation_weeks + 1
    wc = weeks_elapsed % cycle_len  # 0..cycle_len-1
    phase = "deload" if wc == accumulation_weeks else "accumulation"
    return {
        "cycle_num": weeks_elapsed // cycle_len,  # 0-indexé
        "semaine_cycle": wc + 1,                  # 1-indexé pour l'UI (1..cycle_len)
        "accumulation_weeks": accumulation_weeks,
        "cycle_len": cycle_len,
        "phase": phase,
    }


def adjust_sets(base_sets_target: Optional[int], phase_info: dict[str, Any]) -> Optional[int]:
    """Cible de séries de la semaine : +1/sem en accumulation, ~moitié en deload."""
    if base_sets_target is None:
        return None
    if phase_info["phase"] == "deload":
        return max(1, round(base_sets_target / 2))
    # accumulation : semaine 1-indexée -> base + (w - 1)
    return max(1, base_sets_target + (phase_info["semaine_cycle"] - 1))


# ── Store JSON local ──────────────────────────────────────────────────

def mesocycle_file() -> Path:
    from app.core.config import settings
    return settings.data_dir / "entrainement_mesocycle.json"


def _read(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _write(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_state(*, path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """État stocké si un cycle est actif, sinon None."""
    data = _read(path or mesocycle_file())
    return data if data and data.get("active") else None


def start_cycle(
    accumulation_weeks: int = DEFAULT_ACCUMULATION_WEEKS,
    *,
    path: Optional[Path] = None,
    today: Optional[dt.date] = None,
) -> dict[str, Any]:
    today = today or dt.date.today()
    state = {
        "start_date": _monday(today).isoformat(),
        "accumulation_weeks": accumulation_weeks,
        "active": True,
    }
    _write(path or mesocycle_file(), state)
    return state


def stop_cycle(*, path: Optional[Path] = None) -> None:
    _write(path or mesocycle_file(), {"active": False})


def current(*, path: Optional[Path] = None, today: Optional[dt.date] = None) -> Optional[dict[str, Any]]:
    """État courant enrichi (phase + semaine) si un cycle est actif, sinon None."""
    state = get_state(path=path)
    if not state:
        return None
    today = today or dt.date.today()
    start = dt.date.fromisoformat(state["start_date"])
    acc = int(state.get("accumulation_weeks", DEFAULT_ACCUMULATION_WEEKS))
    info = current_phase(start, acc, today)
    return {"active": True, "start_date": state["start_date"], **info}
