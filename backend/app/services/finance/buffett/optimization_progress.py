"""État de progression de l'optimisation de portefeuille (Differential Evolution).

Stocké en mémoire du process : une seule optimisation tourne à la fois (lancée en
background task FastAPI). Lu par l'endpoint ``/portfolio/progress`` et affiché côté
front comme barre de chargement.

Le ``convergence`` (0 → 1) vient du callback de ``scipy.differential_evolution`` :
il croît vers 1 à mesure que la population converge → idéal pour une barre.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_state: dict[str, Any] = {
    "active": False,
    "phase": "idle",        # idle | preparation | optimisation | finalisation
    "iteration": 0,
    "convergence": 0.0,     # 0..1
    "message": "",
    "run_id": None,
}


def reset() -> None:
    with _lock:
        _state.update(active=False, phase="idle", iteration=0,
                      convergence=0.0, message="", run_id=None)


def start(run_id: int | None = None, message: str = "") -> None:
    with _lock:
        _state.update(active=True, phase="preparation", iteration=0,
                      convergence=0.0, message=message, run_id=run_id)


def set_phase(phase: str, message: str = "") -> None:
    with _lock:
        _state["phase"] = phase
        if message:
            _state["message"] = message


def update_de(iteration: int, convergence: float) -> None:
    """Mise à jour pendant le Differential Evolution (1 appel par génération)."""
    with _lock:
        _state["phase"] = "optimisation"
        _state["iteration"] = int(iteration)
        _state["convergence"] = max(0.0, min(float(convergence), 1.0))


def finish(message: str = "") -> None:
    with _lock:
        _state.update(active=False, phase="idle", convergence=1.0, message=message)


def snapshot() -> dict[str, Any]:
    with _lock:
        return dict(_state)
