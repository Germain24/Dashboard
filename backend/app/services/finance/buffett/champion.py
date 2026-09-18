"""Sélection du portefeuille historique servant d'incumbent à l'optimiseur."""

from __future__ import annotations

import math
from typing import Any

from sqlmodel import Session, select

from app.models.finance import BuffettRun, BuffettRunResult, BuffettRunStatus


def allocation_replacement_decision(
    diagnostics: dict[str, Any], *, min_improvement: float = 1e-9
) -> dict[str, Any]:
    """Compare les allocations achetables avec l'objectif réellement optimisé.

    Une égalité doit aussi être persistée : le champion peut venir d'un autre
    run ou avoir été réparé pour les contraintes et les budgets actuels.
    """
    def finite(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    executed = diagnostics.get("executed_portfolio") or {}
    previous = diagnostics.get("previous_run_champion") or {}
    new_score = finite(executed.get("score"))
    previous_score = finite(previous.get("recomputed_executed_score"))
    new_objective = finite(executed.get("objective_score"))
    previous_objective = finite(previous.get("recomputed_executed_objective_score"))
    use_objective = new_objective is not None and previous_objective is not None
    current = new_objective if use_objective else new_score
    baseline = previous_objective if use_objective else previous_score
    previous_valid = bool(previous.get("accepted_as_initial_incumbent")) and (
        previous.get("feasible_under_current_constraints") is not False
        and previous.get("executed_feasible_under_current_constraints") is not False
    )
    if new_score is None:
        accepted, reason = False, "score_exécutable_indisponible"
    elif executed.get("feasible_under_current_constraints") is False:
        accepted, reason = False, "allocation_exécutable_non_admissible"
    elif not previous_valid:
        accepted, reason = True, "aucun_champion_précédent_admissible"
    elif current is None or baseline is None:
        accepted, reason = False, "comparaison_exécutable_indisponible"
    elif current < baseline - 1e-9:
        accepted, reason = False, "objectif_exécutable_inférieur"
    else:
        accepted = True
        reason = (
            "objectif_exécutable_supérieur"
            if current > baseline + max(float(min_improvement), 1e-9)
            else "champion_exécutable_retenu"
        )
    return {
        "accepted": accepted,
        "reason": reason,
        "new_executed_score": new_score,
        "previous_executed_score": previous_score,
        "new_executed_objective_score": new_objective,
        "previous_executed_objective_score": previous_objective,
        "comparison": (
            "executed_objective >= previous_executed_objective - 1e-9"
            if use_objective else "executed_score >= previous_executed_score - 1e-9"
        ),
    }


def portfolio_mode(run: BuffettRun) -> str | None:
    """Retourne le mode de portefeuille documenté par un run."""
    params = run.params_json or {}
    optimization = params.get("optimization") if isinstance(params, dict) else None
    universe = (
        optimization.get("portfolio_universe")
        if isinstance(optimization, dict)
        else None
    ) or {}
    if "include_etfs" not in universe:
        return None
    return "actions_and_etfs" if bool(universe["include_etfs"]) else "actions_only"


def stored_portfolio_score(run: BuffettRun) -> tuple[int, float | None]:
    """Retourne le meilleur score persistant réellement associé à l'allocation.

    Le rang distingue le score exécutable (2) du score continu (1). Quand un
    candidat a été refusé, ``executed_portfolio.score`` décrit le candidat
    refusé et non l'allocation conservée : on reprend alors le score du champion
    précédent, s'il est disponible, et on ignore sinon la valeur du candidat.
    """
    params = run.params_json or {}
    optimization = params.get("optimization") if isinstance(params, dict) else None
    if not isinstance(optimization, dict):
        return 0, None

    replacement = optimization.get("allocation_replacement")
    if isinstance(replacement, dict) and replacement.get("accepted") is False:
        previous = optimization.get("previous_run_champion")
        value = (
            previous.get("recomputed_executed_score")
            if isinstance(previous, dict)
            else None
        )
        if value is None:
            value = replacement.get("previous_executed_score")
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = float("nan")
        return (2, value) if math.isfinite(value) else (0, None)

    executed = optimization.get("executed_portfolio")
    if isinstance(executed, dict):
        try:
            value = float(executed.get("score"))
        except (TypeError, ValueError):
            value = float("nan")
        if math.isfinite(value):
            return 2, value

    benchmarks = optimization.get("benchmarks")
    if isinstance(benchmarks, dict):
        try:
            value = float(benchmarks.get("optimized"))
        except (TypeError, ValueError):
            value = float("nan")
        if math.isfinite(value):
            return 1, value
    return 0, None


def select_best_stored_target(
    session: Session,
    *,
    current_run_id: int,
    requested_mode: str,
    include_legacy_as_requested: bool = False,
) -> dict[str, Any]:
    """Sélectionne l'allocation persistée la plus solide pour un nouveau run.

    Le score exécutable prime sur le score continu, puis la date et l'identifiant
    départagent les anciens runs sans score. Les allocations d'un candidat refusé
    ne sont jamais confondues avec le portefeuille réellement conservé.
    """
    current_run = session.get(BuffettRun, current_run_id)
    candidate_runs: list[BuffettRun] = []
    if current_run is not None:
        candidate_runs.append(current_run)
    candidate_runs.extend(
        list(
            session.exec(
                select(BuffettRun)
                .where(
                    BuffettRun.statut.in_([
                        BuffettRunStatus.TERMINE.value,
                        BuffettRunStatus.ERREUR.value,
                    ])
                )
                .where(BuffettRun.n_tickers_total > 0)
                .where(BuffettRun.n_tickers_analyzed >= BuffettRun.n_tickers_total)
                .where(BuffettRun.id != current_run_id)
                .order_by(BuffettRun.id.desc())
            ).all()
        )
    )

    candidates: list[tuple[int, float, int, int, dict[str, float], str]] = []
    for run in candidate_runs:
        mode = portfolio_mode(run)
        if mode != requested_mode and not (
            include_legacy_as_requested
            and mode is None
            and run.id != current_run_id
        ) and not (run.id == current_run_id and mode is None):
            continue
        rows = list(
            session.exec(
                select(BuffettRunResult)
                .where(BuffettRunResult.run_id == run.id)
                .where(BuffettRunResult.allocation_pct.isnot(None))
            ).all()
        )
        target = {
            str(row.ticker).strip().upper(): float(row.allocation_pct or 0.0) / 100.0
            for row in rows
            if str(row.ticker).strip()
            and float(row.allocation_pct or 0.0) > 0.0
        }
        if not target:
            continue
        rank, score = stored_portfolio_score(run)
        run_date = getattr(run, "run_date", None)
        ordinal = int(run_date.toordinal()) if run_date is not None else 0
        candidates.append(
            (
                rank,
                score if score is not None else float("-inf"),
                ordinal,
                int(run.id or 0),
                target,
                mode or requested_mode,
            )
        )

    if not candidates:
        return {
            "weights": {},
            "source": "workbook",
            "run_id": None,
            "mode": None,
            "score_rank": 0,
            "historical_score": None,
        }

    rank, score, _ordinal, run_id, target, mode = max(
        candidates,
        key=lambda item: item[:4],
    )
    return {
        "weights": target,
        "source": (
            "database_same_mode_best_executable_score"
            if rank == 2
            else "database_same_mode_best_continuous_score"
            if rank == 1
            else "database_same_mode_latest_fallback"
        ),
        "run_id": run_id,
        "mode": mode,
        "score_rank": rank,
        "historical_score": None if rank == 0 else float(score),
    }
