"""État de progression de l'optimisation de portefeuille (Differential Evolution).

Stocké en mémoire du process : une seule optimisation tourne à la fois (lancée en
background task FastAPI). Lu par l'endpoint ``/portfolio/progress`` et affiché côté
front comme barre de chargement.

Le ``convergence`` (0 → 1) vient du callback de ``scipy.differential_evolution`` :
il croît vers 1 à mesure que la population converge → idéal pour une barre.
"""

from __future__ import annotations

import math
import threading
import time
import uuid
from collections import deque
from typing import Any

from app.core.realtime import publish

_lock = threading.Lock()
_MAX_SCORE_HISTORY = 50_000
_score_history: deque[dict[str, Any]] = deque(maxlen=_MAX_SCORE_HISTORY)
_state: dict[str, Any] = {
    "active": False,
    "status": "idle",  # idle | running | stopping | stopped | completed | error
    "termination_reason": None,
    "phase": "idle",  # idle | preparation | initialisation | optimisation | finalisation
    "seed_num": 0,  # numero du seed en cours (1-indexe)
    "completed_seeds": 0,
    "iteration": 0,  # generation DANS le seed en cours (reset a chaque seed)
    "total_iterations": 0,  # generations cumulees, tous seeds confondus
    "initialization_attempt": 0,
    "initialization_max": 0,
    "convergence": 0.0,  # 0..1
    "message": "",
    "run_id": None,
    # Identifie une tentative d'optimisation, pas seulement le run Buffett.
    # Un même run_id peut être repris/recalculé plusieurs fois.
    "optimization_id": None,
    "optimization_started_at": None,
    "stop_requested": False,
    # Meilleur score financier affichable trouve jusqu'ici. L'optimiseur garde
    # ses energies pénalisées en interne, mais ne transmet jamais sa sentinelle
    # d'inadmissibilité (-1e6) à cette progression.
    "best_score": None,
    "seed_score": None,
    # Temperature du recuit adaptatif : elle BAISSE quand le score progresse
    # (exploitation) et MONTE quand il stagne (exploration plus large). None tant
    # qu'aucune generation n'a ete rapportee.
    "temperature": None,
    "phase_done": 0,
    "phase_total": 0,
    "current_item": "",
    "last_activity_at": None,
}


def reset() -> None:
    with _lock:
        _state.update(
            active=False,
            status="idle",
            termination_reason=None,
            phase="idle",
            seed_num=0,
            completed_seeds=0,
            iteration=0,
            total_iterations=0,
            initialization_attempt=0,
            initialization_max=0,
            convergence=0.0,
            message="",
            run_id=None,
            optimization_id=None,
            optimization_started_at=None,
            stop_requested=False,
            best_score=None,
            seed_score=None,
            temperature=None,
            phase_done=0,
            phase_total=0,
            current_item="",
            last_activity_at=time.time(),
        )
        _score_history.clear()
    _publish()


def start(run_id: int | None = None, message: str = "") -> None:
    optimization_id = uuid.uuid4().hex
    with _lock:
        _state.update(
            active=True,
            status="running",
            termination_reason=None,
            phase="preparation",
            seed_num=0,
            completed_seeds=0,
            iteration=0,
            total_iterations=0,
            initialization_attempt=0,
            initialization_max=0,
            convergence=0.0,
            message=message,
            run_id=run_id,
            optimization_id=optimization_id,
            optimization_started_at=time.time(),
            stop_requested=False,
            best_score=None,
            seed_score=None,
            temperature=None,
            phase_done=0,
            phase_total=0,
            current_item="",
            last_activity_at=time.time(),
        )
        _score_history.clear()
    _publish()


def set_phase(
    phase: str,
    message: str = "",
    *,
    done: int | None = None,
    total: int | None = None,
    current_item: str | None = None,
) -> None:
    with _lock:
        phase_changed = _state.get("phase") != phase
        _state["phase"] = phase
        if message:
            _state["message"] = message
        if done is not None:
            _state["phase_done"] = max(0, int(done))
        if total is not None:
            _state["phase_total"] = max(0, int(total))
        if current_item is not None:
            _state["current_item"] = str(current_item)
        elif phase_changed:
            _state["current_item"] = ""
        if phase_changed and done is None:
            _state["phase_done"] = 0
            _state["phase_total"] = 0
        _state["last_activity_at"] = time.time()
    _publish()


def update_initialization(attempt: int, maximum: int, best_score: float | None = None) -> None:
    """Progression de la recherche aléatoire d'un point de départ admissible."""
    with _lock:
        attempt = max(0, int(attempt))
        maximum = max(1, int(maximum))
        # Lors d'un redémarrage inter-seeds, conserver le numéro de seed affiché
        # pendant sa phase d'initialisation. Le premier démarrage part de 0,
        # mais une seed 3 ne doit pas redevenir « seed 0 » pendant ses essais
        # aléatoires, sinon l'interface masque le maximum global/seed courant.
        current_seed_num = max(0, int(_state.get("seed_num") or 0))
        _state["phase"] = "initialisation"
        _state["seed_num"] = current_seed_num
        _state["iteration"] = attempt
        _state["initialization_attempt"] = attempt
        _state["initialization_max"] = maximum
        _state["convergence"] = min(attempt / maximum, 1.0)
        _state["phase_done"] = attempt
        _state["phase_total"] = maximum
        _state["current_item"] = ""
        _state["last_activity_at"] = time.time()
        _state["message"] = f"Recherche aléatoire d'un portefeuille admissible ({attempt}/{maximum})…"
        if best_score is not None and math.isfinite(float(best_score)):
            score = float(best_score)
            previous = _state["best_score"]
            if previous is None or score > float(previous):
                _state["best_score"] = score
    _publish()


def update_de(
    seed_num: int,
    iteration: int,
    convergence: float,
    best_score: float | None = None,
    *,
    seed_score: float | None = None,
    temperature: float | None = None,
    forced_labels: list[str] | None = None,
    forced_action_count: int | None = None,
    forced_etf_count: int | None = None,
) -> None:
    """Mise à jour pendant le Differential Evolution (1 appel par génération).

    ``seed_num`` : numéro du cycle d'optimisation (1-indexé ; il n'augmente plus
    qu'au rafraîchissement d'une composition ETF, la recherche tenant désormais
    en UNE seed continue). ``iteration`` : génération dans ce cycle.
    ``best_score`` : meilleur score financier trouvé jusqu'ici (cf. docstring de
    `_state["best_score"]`). ``seed_score`` est le meilleur score atteint dans la
    seed courante : il est monotone pendant cette seed et est réinitialisé à son
    premier point lorsqu'une nouvelle seed commence. ``temperature`` est celle du
    recuit adaptatif :
    elle baisse quand le score progresse, monte quand il stagne. Chaque
    génération est conservée, plateaux compris, pour tracer la courbe."""
    point: dict[str, Any] | None = None
    with _lock:
        previous_seed_num = max(0, int(_state.get("seed_num") or 0))
        _state["phase"] = "optimisation"
        _state["seed_num"] = int(seed_num)
        _state["completed_seeds"] = max(0, int(seed_num) - 1)
        _state["iteration"] = int(iteration)
        _state["total_iterations"] += 1
        _state["phase_done"] = int(iteration)
        _state["phase_total"] = 0
        _state["current_item"] = ""
        _state["last_activity_at"] = time.time()
        _state["convergence"] = max(0.0, min(float(convergence), 1.0))
        if temperature is not None:
            _state["temperature"] = float(temperature)
        chaleur = (
            "" if temperature is None else f", T={float(temperature):.2f}"
        )
        _state["message"] = (
            f"Optimisation génération {iteration}{chaleur}…"
        )
        if best_score is not None and math.isfinite(float(best_score)):
            score = float(best_score)
            previous = _state["best_score"]
            if previous is None or score > float(previous) + 1e-12:
                _state["best_score"] = score

        # Compatibilité avec les appelants historiques qui ne fournissent que
        # ``best_score`` : leur courbe reste exploitable comme une seule série.
        current_seed_score = best_score if seed_score is None else seed_score
        if current_seed_score is not None:
            score = float(current_seed_score)
            if score == score and score not in (float("inf"), float("-inf")):
                previous_seed_score = _state.get("seed_score")
                if previous_seed_num != int(seed_num) or previous_seed_score is None:
                    _state["seed_score"] = score
                else:
                    _state["seed_score"] = max(float(previous_seed_score), score)
                seed_best_score = float(_state["seed_score"])
                point = {
                    "iteration": int(_state["total_iterations"]),
                    "seed_num": int(seed_num),
                    "seed_iteration": int(iteration),
                    "score": seed_best_score,
                    "global_best_score": (
                        float(_state["best_score"])
                        if _state["best_score"] is not None
                        else score
                    ),
                }
                # La courbe du front est colorée par la température de CETTE
                # génération. Clé ajoutée seulement quand l'appelant la fournit :
                # les appelants historiques gardent leur forme exacte, et on
                # n'attribue jamais à un point une température qui n'est pas la
                # sienne (ne pas retomber sur `_state`, qui garde la dernière
                # connue).
                if temperature is not None:
                    point["temperature"] = float(temperature)
                if forced_labels:
                    point["forced_labels"] = [
                        str(label) for label in forced_labels if str(label).strip()
                    ]
                    point["forced_action_count"] = max(
                        0, int(forced_action_count or 0)
                    )
                    point["forced_etf_count"] = max(0, int(forced_etf_count or 0))
                _score_history.append(point)
    _publish([point] if point is not None else [])


def request_stop() -> bool:
    """Demande l'arrêt de l'optimisation en cours.

    La préparation s'interrompt après le lot réseau courant ; le DE s'interrompt
    après la génération courante. Le meilleur portefeuille déjà trouvé est
    conservé lorsqu'il existe.
    """
    with _lock:
        if not _state.get("active"):
            return False
        _state["stop_requested"] = True
        _state["status"] = "stopping"
        _state["message"] = "Arrêt demandé — finalisation du meilleur portefeuille…"
        _state["last_activity_at"] = time.time()
    _publish()
    return True


def finish(
    message: str = "",
    *,
    status: str = "completed",
    termination_reason: str | None = None,
) -> None:
    with _lock:
        _state.update(
            active=False, phase="idle", convergence=1.0, message=message,
            status=status, termination_reason=termination_reason,
            current_item="", last_activity_at=time.time(),
        )
    _publish()


def reset_objective_score(message: str = "") -> None:
    """Nouvel objectif au sein du même run (composition ETF actualisée).

    L'historique et la numérotation des seeds restent continus, mais un score
    calculé avec les anciennes expositions ne peut plus être le ``global_best``
    du nouvel objectif.
    """
    with _lock:
        _state["best_score"] = None
        _state["seed_score"] = None
        _state["convergence"] = 0.0
        _state["last_activity_at"] = time.time()
        if message:
            _state["message"] = message
    _publish()


def _publish(score_history: list[dict[str, Any]] | None = None) -> None:
    data = snapshot()
    if score_history is not None:
        data["score_history"] = score_history
    publish(
        "finance.optimization.progress",
        data=data,
        invalidate=[["finance", "buffett"]],
    )


def snapshot(history_after: int | None = None) -> dict[str, Any]:
    """Retourne l'état courant et, sur demande, les points après une itération.

    L'historique n'est pas copié par défaut: ``snapshot()`` est appelé à chaque
    génération par le contrôle d'arrêt et doit rester constant en coût.
    """
    with _lock:
        result = dict(_state)
        phase_total = max(0, int(result.get("phase_total") or 0))
        if phase_total:
            phase_done = min(max(0, int(result.get("phase_done") or 0)), phase_total)
            result["progress_pct"] = round(phase_done / phase_total * 100, 1)
        else:
            result["progress_pct"] = round(
                float(result.get("convergence", 0.0)) * 100,
                1,
            )
        if history_after is not None:
            after = max(0, int(history_after))
            result["score_history"] = [
                dict(point) for point in _score_history if int(point["iteration"]) > after
            ]
        last_activity = result.get("last_activity_at")
        seconds = max(0.0, time.time() - float(last_activity)) if last_activity else 0.0
        result["seconds_since_activity"] = round(seconds, 1)
        result["stalled"] = bool(result.get("active") and seconds >= 120.0)
        return result
