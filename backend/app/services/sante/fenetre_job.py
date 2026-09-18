"""Génération asynchrone d'une fenêtre nutrition.

Depuis l'élargissement du catalogue aux produits Super C, une génération demande
~2 min (mesuré : 127 s pour 400 aliments présélectionnés, contre 13 s avec les
seuls 116 aliments curés). C'est sous le délai d'attente du client (180 s), mais
la marge est trop mince pour en dépendre : un jour de charge, l'utilisateur
verrait un échec alors que le calcul aboutit côté serveur.

Même patron que `superc_cart.py`, déjà en place et éprouvé : un dictionnaire de
jobs en mémoire, un thread par job, un seul job actif à la fois, et un endpoint
d'interrogation. Pas de file d'attente ni de dépendance nouvelle — une seule
optimisation à la fois suffit, et deux générations concurrentes se voleraient de
toute façon le CPU (c'est précisément ce qui avait fait exploser les temps quand
le scrape tournait pendant SLSQP).
"""
from __future__ import annotations

import copy
import datetime as dt
import threading
import uuid
from typing import Any, Optional

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_active_job_id: str | None = None
_ACTIVE = frozenset({"queued", "running"})

#: Jobs conservés en mémoire (les plus anciens sont purgés).
_MAX_JOBS = 10


def _update(job_id: str, **patch: Any) -> None:
    with _lock:
        if job_id in _jobs:
            # Une demande d'arrêt est monotone. La progression de l'essai déjà
            # engagé ne doit jamais pouvoir la remettre à False avant que la
            # boucle d'optimisation ne la consulte.
            if _jobs[job_id].get("stop_requested"):
                patch.pop("stop_requested", None)
            _jobs[job_id].update(patch)


def _run(
    job_id: str,
    day: Optional[dt.date],
    poids: Optional[float],
    force: bool,
    refresh_prices: bool,
) -> None:
    global _active_job_id
    # Session dédiée : le thread ne doit RIEN partager avec celle de la requête
    # HTTP, qui est fermée dès la réponse 202 renvoyée.
    from sqlmodel import Session

    from app.core.db import engine

    try:
        _update(
            job_id,
            status="running",
            message=(
                (
                    "Vérification des prix Super C dans la fenêtre Chrome dédiée… "
                    "Si la sécurité apparaît, termine-la dans Chrome."
                ) if refresh_prices else
                "Utilisation des prix Super C déjà enregistrés…"
            ),
        )

        def on_progress(progress: dict[str, Any]) -> None:
            coverage = progress.get("best_coverage")
            cost = progress.get("best_cost")
            ratio = progress.get("best_ratio")
            best = ""
            if coverage is not None and cost is not None:
                ratio_label = (
                    f" · {float(ratio):.3f} pt/$" if ratio is not None else ""
                )
                best = (
                    f" · meilleur ratio {float(coverage) * 100:.1f}% / "
                    f"{float(cost):.2f} ${ratio_label}"
                )
            if progress.get("phase") == "simplification":
                message = (
                    f"Simplification {progress.get('prune_attempt', 0)}/"
                    f"{progress.get('prune_total', 0)}"
                    f" · {len(progress.get('removed_foods', []))} aliments retirés{best}"
                )
            else:
                maximum = progress.get("max_attempts")
                maximum_label = str(maximum) if maximum is not None else "∞"
                message = (
                    f"Recherche {progress.get('attempt', 0)}/{maximum_label}"
                    f" · {progress.get('solutions_found', 0)} solutions{best}"
                )
            _update(
                job_id,
                status="running",
                message=message,
                **progress,
            )

        def should_stop() -> bool:
            with _lock:
                return bool(_jobs.get(job_id, {}).get("stop_requested"))

        with Session(engine) as session:
            from app.services.sante.fenetre_service import generate_window

            # `generate_window` vérifie déjà les prix exactement une fois avant
            # de construire son catalogue. Le refaire ici lançait deux Chrome
            # Super C successifs pour chaque clic et doublait les challenges.
            wp = generate_window(
                session, day=day, poids=poids, force=force,
                refresh_prices=refresh_prices,
                progress_cb=on_progress, should_stop=should_stop,
                continuous_search=True,
            )
            was_stopped = should_stop()
            _update(
                job_id,
                status="completed",
                message=(
                    f"Meilleur plan conservé après arrêt ({wp.length} jours)."
                    if was_stopped else
                    f"Fenêtre prête ({wp.length} jours, {len(wp.food_set)} aliments)."
                ),
                anchor_date=wp.anchor_date.isoformat(),
                stopped=was_stopped,
            )
    except Exception as exc:
        _update(job_id, status="failed", message="Échec de la génération.", error=str(exc))
    finally:
        with _lock:
            if _active_job_id == job_id:
                _active_job_id = None


def start_generate(
    day: Optional[dt.date] = None,
    poids: Optional[float] = None,
    force: bool = False,
    refresh_prices: bool = True,
) -> tuple[dict[str, Any], bool]:
    """Lance une génération, ou retourne le job déjà actif.

    Retourne `(job, cree)`. `cree=False` signale que l'appel a rejoint un job en
    cours : deux clics sur « Générer » ne lancent pas deux optimisations.
    """
    global _active_job_id
    with _lock:
        if _active_job_id and _jobs.get(_active_job_id, {}).get("status") in _ACTIVE:
            return copy.deepcopy(_jobs[_active_job_id]), False
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "status": "queued",
            "message": "Préparation du catalogue…",
            "anchor_date": None,
            "error": None,
            "stop_requested": False,
            "stopped": False,
            "attempt": 0,
            "max_attempts": None,
            "solutions_found": 0,
            "pareto_solutions": 0,
            "stagnation": 0,
            "patience": 0,
            "convergence": 0.0,
            "temperature": None,
            "best_ratio": None,
            "best_coverage": None,
            "best_cost": None,
            "best_items": [],
            "phase": "search",
            "prune_attempt": 0,
            "prune_total": 0,
            "removed_foods": [],
        }
        _jobs[job_id] = job
        _active_job_id = job_id
        for old_id in list(_jobs)[:-_MAX_JOBS]:
            if old_id != job_id:
                _jobs.pop(old_id, None)
    threading.Thread(
        target=_run, args=(job_id, day, poids, force, refresh_prices),
        daemon=True, name=f"fenetre-gen-{job_id[:8]}",
    ).start()
    return copy.deepcopy(job), True


def get_generate(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return copy.deepcopy(job) if job is not None else None


def get_active_generate() -> dict[str, Any] | None:
    """Job actif pour permettre à l'interface de le rejoindre après navigation."""
    with _lock:
        if not _active_job_id:
            return None
        job = _jobs.get(_active_job_id)
        if job is None or job.get("status") not in _ACTIVE:
            return None
        return copy.deepcopy(job)


def request_stop(job_id: str) -> dict[str, Any] | None:
    """Demande un arrêt coopératif; le meilleur plan trouvé sera persisté."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        if job.get("status") in _ACTIVE:
            job["stop_requested"] = True
            job["message"] = "Arrêt demandé… finalisation du meilleur plan trouvé."
        return copy.deepcopy(job)


def _reset_for_tests() -> None:
    global _active_job_id
    with _lock:
        _jobs.clear()
        _active_job_id = None
