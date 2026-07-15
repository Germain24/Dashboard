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
    "seed_num": 0,          # numero du seed en cours (1-indexe)
    "iteration": 0,         # generation DANS le seed en cours (reset a chaque seed)
    "convergence": 0.0,     # 0..1
    "message": "",
    "run_id": None,
    "stop_requested": False,
    # Meilleur score d'optimisation trouve jusqu'ici (objectif STARR penalise,
    # cf. optimizer.py `neg_obj` -- pas un STARR pur, les contraintes de
    # cardinalite/defensif/pays sont incluses). Croissant au cours du run,
    # partage entre TOUS les seeds (jamais remis a zero) -- pour le graphe
    # d'evolution en direct cote front.
    "best_score": None,
}


def reset() -> None:
    with _lock:
        _state.update(active=False, phase="idle", seed_num=0, iteration=0,
                      convergence=0.0, message="", run_id=None, stop_requested=False,
                      best_score=None)


def start(run_id: int | None = None, message: str = "") -> None:
    with _lock:
        _state.update(active=True, phase="preparation", seed_num=0, iteration=0,
                      convergence=0.0, message=message, run_id=run_id, stop_requested=False,
                      best_score=None)


def set_phase(phase: str, message: str = "") -> None:
    with _lock:
        _state["phase"] = phase
        if message:
            _state["message"] = message


def update_de(seed_num: int, iteration: int, convergence: float, best_score: float | None = None) -> None:
    """Mise à jour pendant le Differential Evolution (1 appel par génération).

    ``seed_num`` : numéro du seed en cours (1-indexé, augmente à chaque
    redémarrage du DE). ``iteration`` : génération dans CE seed (repart de 1 à
    chaque nouveau seed). ``best_score`` : meilleur score trouvé jusqu'ici,
    tous seeds confondus (cf. docstring de `_state["best_score"]`)."""
    with _lock:
        _state["phase"] = "optimisation"
        _state["seed_num"] = int(seed_num)
        _state["iteration"] = int(iteration)
        _state["convergence"] = max(0.0, min(float(convergence), 1.0))
        if best_score is not None:
            _state["best_score"] = float(best_score)


def request_stop() -> None:
    """Demande l'arrêt de l'optimisation en cours -- pris en compte à la fin de
    la génération en cours (jamais au milieu d'une), par les deux points
    d'entrée DE (run automatique et bouton manuel « Créer le portefeuille
    optimal »). Le meilleur portefeuille trouvé jusque-là est conservé."""
    with _lock:
        _state["stop_requested"] = True


def finish(message: str = "") -> None:
    with _lock:
        _state.update(active=False, phase="idle", convergence=1.0, message=message)


def snapshot() -> dict[str, Any]:
    with _lock:
        return dict(_state)
