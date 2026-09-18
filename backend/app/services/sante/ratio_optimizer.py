"""Maximise le ratio couverture-micro / coût (spec §2) par balayage borné du
poids-prix passé à l'optimiseur SLSQP, en sélectionnant la solution au meilleur
VRAI ratio. Robuste : réutilise entièrement `optimize_nutrition` (contraintes,
bornes, snap MinQty) sans en réécrire la physique.
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Callable, Optional

import pandas as pd

from app.services.sante.coverage import coverage_score
from app.services.sante.optimizer import optimize_nutrition
from app.services.sante.pantry_fenetre import normalize_stock_lots
from app.services.sante.totals import calculate_plan_totals

# Première exploration logarithmique, du plus permissif au plus économe. Elle
# est ensuite prolongée par des poids intercalaires et des multi-départs jusqu'à
# convergence de la frontière couverture/coût (au lieu de six essais fixes).
DEFAULT_PRICE_WEIGHTS: tuple[float, ...] = (
    0.0001, 0.0003, 0.001, 0.003, 0.01, 0.02, 0.04, 0.08,
    0.12, 0.18, 0.25, 0.4, 0.6, 0.9, 1.2, 1.8, 2.7, 4.0,
    8.0, 16.0, 32.0, 64.0,
)
MIN_SEARCH_PASSES = 24
MAX_SEARCH_PASSES = 96
CONVERGENCE_PATIENCE = 24
MIN_ACCEPTABLE_COVERAGE = 0.90
_GOLDEN_FRACTION = 0.6180339887498949


_ZERO_COST_FLOOR = 0.01  # CAD; keeps a valid free-stock plan's ratio finite.


def _purchase_cost(
    plan: list[dict], df: pd.DataFrame,
    pantry_stock: Optional[dict[str, list[dict[str, float]]]] = None,
) -> float:
    """Coût économique consommé : stock à 0/50 %, surplus à 100 %.

    This is the cost used to compare nutritional plans. It stays proportional
    to grams, matching the user's 500 g at half price + 100 g at full price
    example. Cash checkout/package counts are calculated separately.
    """
    total = 0.0
    pantry_stock = pantry_stock or {}
    for item in plan:
        name = str(item["Aliment"])
        grams = max(0.0, float(item["Quantite_g"]))
        try:
            unit_price = max(0.0, float(df.loc[name, "Prix"]))
        except (KeyError, TypeError, ValueError):
            unit_price = max(0.0, float(item.get("Prix") or 0.0) * 100.0 / max(grams, 1e-9))
        remaining = grams / 100.0
        cost = remaining * unit_price
        for stock_units, factor in normalize_stock_lots(pantry_stock.get(name)):
            used = min(remaining, stock_units)
            cost -= used * unit_price * (1.0 - factor)
            remaining -= used
            if remaining <= 1e-12:
                break
        total += cost
    return total


def _cash_purchase_cost(
    plan: list[dict], df: pd.DataFrame,
    pantry_stock: Optional[dict[str, list[dict[str, float]]]] = None,
) -> float:
    """Estimated checkout cost for quantities not covered by inventory."""
    total = 0.0
    pantry_stock = pantry_stock or {}
    package_aware = {"PackagePrice", "PackageWeightG"}.issubset(df.columns)
    for item in plan:
        name = str(item["Aliment"])
        grams = max(0.0, float(item["Quantite_g"]))
        stock_g = sum(units for units, _factor in normalize_stock_lots(pantry_stock.get(name))) * 100.0
        deficit_g = max(0.0, grams - stock_g)
        if deficit_g <= 1e-9:
            continue
        if not package_aware:
            try:
                unit_price = float(df.loc[name, "Prix"])
            except (KeyError, TypeError, ValueError):
                unit_price = float(item.get("Prix") or 0.0) * 100.0 / max(grams, 1e-9)
            total += deficit_g / 100.0 * max(0.0, unit_price)
            continue
        row = df.loc[name]
        package_price = float(row.get("PackagePrice", 0.0) or 0.0)
        package_g = float(row.get("PackageWeightG", 0.0) or 0.0)
        if package_price > 0.0 and package_g > 0.0:
            total += math.ceil(max(0.0, deficit_g - 1e-9) / package_g) * package_price
        else:
            total += deficit_g / 100.0 * max(0.0, float(row["Prix"]))
    return total


def _plan_metrics(
    plan: list[dict], df: pd.DataFrame, targets: dict[str, float],
    pantry_stock: Optional[dict[str, list[dict[str, float]]]] = None,
) -> dict[str, Any] | None:
    """Mesure un plan selon le même score/coût que la recherche globale."""
    totals = calculate_plan_totals(plan, df)
    if (
        totals.get("Calories", 0.0) < float(targets.get("Calories", 0.0)) * 0.98
        or totals.get("Protéines", 0.0) < float(targets.get("Protéines", 0.0)) * 0.98
    ):
        return None
    cost = _purchase_cost(plan, df, pantry_stock)
    cash_cost = _cash_purchase_cost(plan, df, pantry_stock)
    cov = coverage_score(totals, targets)
    nutrition_score = cov.get("nutrition_balance_mean", cov["coverage_mean"])
    return {
        "couverture_moyenne": cov["coverage_mean"],
        "pct_micros_atteints": cov["pct_micros_atteints"],
        "equilibre_macros": cov.get("macro_balance_mean", 0.0),
        "equilibre_moyen": nutrition_score,
        "cout_total": cost,
        "cout_a_payer_estime": cash_cost,
        "ratio": nutrition_score / max(cost, _ZERO_COST_FLOOR),
        "sous_couverts": cov["sous_couverts"],
    }


def prune_redundant_foods(
    plan: list[dict], metrics: dict[str, Any], df: pd.DataFrame,
    targets: dict[str, float], *, price_weight: float,
    micro_weight_mult: Optional[dict[str, float]] = None,
    pantry_stock: Optional[dict[str, list[dict[str, float]]]] = None,
    quantity_days: int = 1,
    progress_cb: Optional[Callable[[dict[str, Any]], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> tuple[list[dict], dict[str, Any], list[str]]:
    """Teste la suppression de chaque aliment, du plus cher/kg au moins cher.

    Après retrait, SLSQP ne voit que les aliments déjà présents : il peut en
    augmenter les portions, mais ne peut pas réintroduire l'aliment testé ni
    ajouter une nouveauté. Une suppression n'est gardée que si elle améliore le
    vrai ratio avec au moins 90 % de couverture.
    """
    incumbent_plan = plan
    incumbent_metrics = metrics
    removed: list[str] = []
    original_names = {str(item["Aliment"]) for item in plan}
    # `Prix` est exprimé en CAD/100 g dans le catalogue, donc son ordre est
    # exactement celui du CAD/kg. La quantité ne sert que de départage : parmi
    # deux aliments au même prix/kg, on essaie d'abord le petit résidu.
    def removal_priority(item: dict) -> tuple[float, float]:
        name = str(item["Aliment"])
        try:
            price_per_100g = float(df.loc[name, "Prix"])
        except (KeyError, TypeError, ValueError):
            price_per_100g = 0.0
        return (-price_per_100g, float(item["Quantite_g"]))

    ordered = [
        str(item["Aliment"])
        for item in sorted(plan, key=removal_priority)
    ]
    total = len(ordered)
    for index, excluded in enumerate(ordered, start=1):
        if should_stop is not None and should_stop():
            break
        current_names = {str(item["Aliment"]) for item in incumbent_plan}
        if excluded not in current_names:
            continue
        remaining = [
            str(item["Aliment"]) for item in incumbent_plan
            if str(item["Aliment"]) != excluded
        ]
        if not remaining:
            continue
        subset = df.loc[remaining].copy()
        initial = {
            str(item["Aliment"]): float(item["Quantite_g"])
            for item in incumbent_plan if str(item["Aliment"]) != excluded
        }
        candidate, _warning = optimize_nutrition(
            subset, targets, budget_max_daily=1e9, seed=None,
            price_weight=price_weight, micro_weight_mult=micro_weight_mult,
            pantry_stock=pantry_stock, quantity_days=quantity_days,
            initial_quantities=initial,
        )
        candidate_metrics = (
            _plan_metrics(candidate, subset, targets, pantry_stock)
            if candidate is not None else None
        )
        if (
            candidate is not None
            and candidate_metrics is not None
            and candidate_metrics["couverture_moyenne"] >= MIN_ACCEPTABLE_COVERAGE
            and candidate_metrics["ratio"] > incumbent_metrics["ratio"] + 1e-9
        ):
            incumbent_plan = candidate
            incumbent_metrics = candidate_metrics
            removed = sorted(original_names - {
                str(item["Aliment"]) for item in incumbent_plan
            })
        if progress_cb is not None:
            try:
                progress_cb({
                    "phase": "simplification",
                    "prune_attempt": index,
                    "prune_total": total,
                    "removed_foods": list(removed),
                    "best_ratio": incumbent_metrics["ratio"],
                    "best_coverage": incumbent_metrics.get(
                        "equilibre_moyen", incumbent_metrics["couverture_moyenne"]
                    ),
                    "best_cost": incumbent_metrics["cout_total"],
                    "best_items": [
                        {"aliment": str(item["Aliment"]),
                         "quantite_g": round(float(item["Quantite_g"]), 1)}
                        for item in incumbent_plan
                    ],
                })
            except Exception:
                pass
    return incumbent_plan, incumbent_metrics, removed


def optimize_ratio(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float] = None,
    seed: Optional[int] = None,
    micro_weight_mult: Optional[dict[str, float]] = None,
    pantry_stock: Optional[dict[str, list[dict[str, float]]]] = None,
    price_weights: tuple[float, ...] = DEFAULT_PRICE_WEIGHTS,
    quantity_days: int = 1,
    min_search_passes: int = MIN_SEARCH_PASSES,
    max_search_passes: int = MAX_SEARCH_PASSES,
    convergence_patience: int = CONVERGENCE_PATIENCE,
    progress_cb: Optional[Callable[[dict[str, Any]], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    continuous_until_stopped: bool = False,
    refine: bool = True,
) -> tuple[list[dict[str, Any]] | None, str, dict]:
    candidates: list[tuple[list[dict], str, dict]] = []
    signatures: set[tuple[tuple[str, float], ...]] = set()
    pareto: list[tuple[float, float]] = []
    last_warning = ""
    # Calories & protéines = MINIMUMS STRICTS (choix user 2026-07-23) : un plan qui
    # les rate a un score (ratio) de 0 -> jamais choisi devant un plan qui les
    # atteint. Sinon le ratio pur dégénère vers un plan sous-calorique / pauvre en
    # protéines (il « gagne » en ne dépensant presque rien).
    cal_target = float(targets.get("Calories", 0.0))
    prot_target = float(targets.get("Protéines", 0.0))
    if not price_weights:
        price_weights = DEFAULT_PRICE_WEIGHTS
    min_passes = max(len(price_weights), int(min_search_passes), 1)
    max_passes = max(min_passes, int(max_search_passes))
    patience = max(1, int(convergence_patience))
    lo_log = math.log10(min(price_weights))
    hi_log = math.log10(max(price_weights))
    stale = 0
    temperature = 0.25
    best_weight = math.sqrt(min(price_weights) * max(price_weights))
    attempts_done = 0
    stopped = False
    simplified_signatures: set[tuple[tuple[str, float], ...]] = set()

    def search_weight(attempt: int) -> float:
        if attempt < len(price_weights):
            return float(price_weights[attempt])
        # Recuit adaptatif comme pour Finance : autour du meilleur poids connu,
        # une température basse affine localement; après stagnation elle monte
        # et réexplore une zone logarithmique plus large.
        fraction = ((attempt - len(price_weights) + 1) * _GOLDEN_FRACTION) % 1.0
        signed = fraction * 2.0 - 1.0
        centre = math.log10(best_weight)
        return 10.0 ** max(lo_log, min(hi_log, centre + signed * temperature * (hi_log - lo_log)))

    def extends_pareto(coverage: float, cost: float) -> bool:
        nonlocal pareto
        if any(c >= coverage - 1e-9 and p <= cost + 1e-9 for c, p in pareto):
            return False
        pareto = [
            (c, p) for c, p in pareto
            if not (coverage >= c - 1e-9 and cost <= p + 1e-9)
        ]
        pareto.append((coverage, cost))
        return True

    def best_candidate() -> tuple[list[dict], str, dict] | None:
        if not candidates:
            return None
        # Vrai ratio score/coût, avec seulement un garde-fou nutritionnel absolu.
        # L'ancienne règle « à 5 points du meilleur » déplaçait continuellement
        # le seuil vers 95 % dès qu'une solution à 100 % apparaissait et pouvait
        # donc rejeter un excellent 92 % deux fois moins cher.
        nutritious = [
            c for c in candidates
            if c[2]["couverture_moyenne"] >= MIN_ACCEPTABLE_COVERAGE
        ]
        if nutritious:
            return max(nutritious, key=lambda c: c[2]["ratio"])
        # Avant d'avoir atteint le plancher nutritionnel, ne pas optimiser le
        # ratio : cela élisait un panier médiocre à 72 % simplement parce qu'il
        # coûtait moins cher qu'un panier à 85 %. On se rapproche d'abord de
        # 90 %, puis seulement on optimise score/coût.
        return max(candidates, key=lambda c: (
            c[2].get("equilibre_moyen", c[2]["couverture_moyenne"]),
            -c[2]["cout_total"],
        ))

    def simplify_candidate_once(
        candidate: tuple[list[dict], str, dict] | None,
    ) -> bool:
        """Simplifie une fois un panier et indique s'il étend la frontière."""
        if candidate is None:
            return False
        incumbent, warning, incumbent_metrics = candidate
        signature = tuple(sorted(
            (str(item["Aliment"]), round(float(item["Quantite_g"]), 1))
            for item in incumbent
        ))
        if signature in simplified_signatures:
            return False
        simplified_signatures.add(signature)
        selected_weight = float(incumbent_metrics.get("_price_weight", best_weight))

        def emit_prune_progress(update: dict[str, Any]) -> None:
            """Affiche l'avancement sans faire passer le panier testé pour le meilleur.

            Depuis que chaque solution, y compris dominée, est simplifiée, le
            callback brut de ``prune_redundant_foods`` contient les métriques de
            cette solution locale. L'interface l'étiquetait alors « meilleur »
            et pouvait sembler remplacer un excellent ratio par un score brut
            plus cher. Les métriques gagnantes viennent toujours de
            ``best_candidate``; seuls phase/compteur/retraits viennent du prune.
            """
            if progress_cb is None:
                return
            current_best = best_candidate()
            if current_best is not None:
                best_plan, _best_warning, best_metrics = current_best
                update = {
                    **update,
                    "best_ratio": best_metrics.get("ratio"),
                    "best_coverage": best_metrics.get(
                        "equilibre_moyen", best_metrics.get("couverture_moyenne")
                    ),
                    "best_cost": best_metrics.get("cout_total"),
                    "best_items": [
                        {
                            "aliment": str(item["Aliment"]),
                            "quantite_g": round(float(item["Quantite_g"]), 1),
                        }
                        for item in best_plan
                    ],
                }
            progress_cb(update)

        simplified, metrics, removed = prune_redundant_foods(
            incumbent, incumbent_metrics, df, targets,
            price_weight=selected_weight,
            micro_weight_mult=micro_weight_mult,
            pantry_stock=pantry_stock,
            quantity_days=quantity_days,
            progress_cb=emit_prune_progress,
            should_stop=should_stop,
        )
        if not removed:
            return False
        metrics = {
            **metrics,
            "_price_weight": selected_weight,
            "removed_foods": list(removed),
        }
        simplified_signature = tuple(sorted(
            (str(item["Aliment"]), round(float(item["Quantite_g"]), 1))
            for item in simplified
        ))
        frontier_changed = False
        if simplified_signature not in signatures:
            signatures.add(simplified_signature)
            candidates.append((simplified, warning, metrics))
            frontier_changed = extends_pareto(
                float(metrics.get("equilibre_moyen", metrics["couverture_moyenne"])),
                float(metrics["cout_total"]),
            )
        return frontier_changed

    def emit_progress(pw: float) -> None:
        if progress_cb is None:
            return
        best = best_candidate()
        metrics = best[2] if best else {}
        best_items = [] if best is None else [
            {
                "aliment": str(item["Aliment"]),
                "quantite_g": round(float(item["Quantite_g"]), 1),
            }
            for item in best[0]
        ]
        try:
            progress_cb({
                "attempt": attempts_done,
                "max_attempts": None if continuous_until_stopped else max_passes,
                "solutions_found": len(candidates),
                "pareto_solutions": len(pareto),
                "stagnation": stale,
                "patience": patience,
                "convergence": min(stale / patience, 1.0),
                "temperature": temperature,
                "price_weight": pw,
                "best_ratio": metrics.get("ratio"),
                "best_coverage": metrics.get(
                    "equilibre_moyen", metrics.get("couverture_moyenne")
                ),
                "best_cost": metrics.get("cout_total"),
                "best_items": best_items,
            })
        except Exception:
            pass  # l'affichage de progression ne doit jamais casser le solveur

    # Comme l'optimisation Finance, le job asynchrone peut poursuivre les cycles
    # indéfiniment jusqu'au bouton Arrêter. Sans callback d'arrêt, on conserve
    # toujours le garde-fou borné pour éviter un appel programmatique infini.
    continuous = bool(continuous_until_stopped and should_stop is not None)
    attempt_range = itertools.count() if continuous else range(max_passes)
    for attempt in attempt_range:
        if attempt > 0 and candidates and should_stop is not None and should_stop():
            stopped = True
            break
        if continuous and refine and candidates and stale >= patience:
            simplify_candidate_once(best_candidate())
            stale = 0
            # Le bassin courant a été exploité : on réchauffe pour repartir à
            # la recherche d'un autre panier dominant.
            temperature = min(1.0, temperature + 0.25)
            if should_stop is not None and should_stop():
                stopped = True
                break
        pw = search_weight(attempt)
        # Même préférence gustative pour tous les essais, mais point de départ
        # différent : on explore les optima locaux sans changer la fonction à
        # optimiser en cours de recherche.
        start_seed = ((seed or 0) + 104729 * (attempt + 1)) % (2**32)
        # Étape 0 : base uniforme demandée par l'utilisateur. SLSQP part avec
        # 200 g de chaque aliment sur la fenêtre puis réduit/élimine ce qui est
        # inutile. ``optimize_nutrition`` clampe lui-même ces valeurs aux
        # plafonds propres aux condiments, suppléments et groupes alimentaires.
        # Les essais suivants retrouvent leurs départs aléatoires diversifiés.
        initial_quantities = (
            {str(name): 200.0 for name in df.index} if attempt == 0 else None
        )
        plan, warning = optimize_nutrition(
            df, targets, budget_max_daily=budget_max_daily, seed=seed,
            price_weight=pw, micro_weight_mult=micro_weight_mult,
            pantry_stock=pantry_stock, quantity_days=quantity_days,
            initial_seed=start_seed,
            initial_quantities=initial_quantities,
        )
        attempts_done = attempt + 1
        last_warning = warning
        if plan is None:
            stale += 1
            temperature = min(1.0, temperature + 0.04)
            emit_progress(pw)
            if not continuous and attempt + 1 >= min_passes and stale >= patience:
                break
            continue
        signature = tuple(sorted(
            (str(item["Aliment"]), round(float(item["Quantite_g"]), 1))
            for item in plan
        ))
        if signature in signatures:
            stale += 1
            temperature = min(1.0, temperature + 0.04)
            emit_progress(pw)
            if not continuous and attempt + 1 >= min_passes and stale >= patience:
                break
            continue
        signatures.add(signature)
        totals = calculate_plan_totals(plan, df)
        cost = _purchase_cost(plan, df, pantry_stock)
        cash_cost = _cash_purchase_cost(plan, df, pantry_stock)
        cov = coverage_score(totals, targets)
        nutrition_score = cov.get("nutrition_balance_mean", cov["coverage_mean"])
        ratio = nutrition_score / max(cost, _ZERO_COST_FLOOR)
        if (totals.get("Calories", 0.0) < cal_target * 0.98
                or totals.get("Protéines", 0.0) < prot_target * 0.98):
            ratio = 0.0   # minimum strict raté -> score nul
        if ratio > 0.0:
            metrics = {
                "couverture_moyenne": cov["coverage_mean"],
                "pct_micros_atteints": cov["pct_micros_atteints"],
                "equilibre_macros": cov.get("macro_balance_mean", 0.0),
                "equilibre_moyen": nutrition_score,
                "cout_total": cost,
                "cout_a_payer_estime": cash_cost,
                "ratio": ratio,
                "sous_couverts": cov["sous_couverts"],
                # Interne : permet de reprendre exactement le compromis qui a
                # produit le gagnant pendant la passe de simplification.
                "_price_weight": pw,
            }
            candidate = (plan, warning, metrics)
            candidates.append(candidate)
            frontier_extended = extends_pareto(nutrition_score, cost)
            # Même un panier actuellement dominé peut devenir dominant une fois
            # ses produits superflus retirés et les portions restantes
            # réoptimisées. En recherche continue, chaque solution distincte
            # reçoit donc sa propre passe complète de simplification.
            if continuous and refine:
                frontier_extended = (
                    simplify_candidate_once(candidate) or frontier_extended
                )
            if frontier_extended:
                stale = 0
                best_weight = pw
                temperature = max(0.05, temperature * 0.7)
            else:
                stale += 1
                temperature = min(1.0, temperature + 0.04)
        else:
            stale += 1
            temperature = min(1.0, temperature + 0.04)
        emit_progress(pw)
        if not continuous and attempt + 1 >= min_passes and stale >= patience:
            break
    if not candidates:
        return None, (last_warning or "Optimisation impossible sur tout le balayage."), {}
    # Sélection réelle score/coût, sous le plancher nutritionnel absolu de 90 %.
    # Calories et protéines restent en plus des minimums stricts.
    best = best_candidate()
    assert best is not None
    plan, warning, raw_metrics = best
    selected_weight = float(raw_metrics.get("_price_weight", best_weight))
    metrics = {key: value for key, value in raw_metrics.items() if key != "_price_weight"}
    removed_foods: list[str] = list(raw_metrics.get("removed_foods", []))
    # En continu, Arrêter doit rendre la main : la simplification a déjà lieu
    # à chaque nouvelle frontière (et à la convergence) et ne doit pas
    # redémarrer seulement après le clic.
    if refine and len(plan) > 1 and not stopped:
        plan, metrics, removed_foods = prune_redundant_foods(
            plan, metrics, df, targets,
            price_weight=selected_weight,
            micro_weight_mult=micro_weight_mult,
            pantry_stock=pantry_stock,
            quantity_days=quantity_days,
            progress_cb=progress_cb,
        )
    metrics = {
        **metrics,
        "search_attempts": attempts_done,
        "solutions_found": len(candidates),
        "pareto_solutions": len(pareto),
        "temperature": temperature,
        "stopped": stopped,
        "removed_foods": removed_foods,
    }
    return plan, warning, metrics
