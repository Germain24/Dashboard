import pandas as pd
import pytest

from app.services.sante.ratio_optimizer import optimize_ratio


def _df():
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres", "Fer"]
    data = {
        "Legume":  [50.0, 3.0, 0.5, 8.0, 0.4, 80.0, 6.0, 3.0],
        "Riz":     [130.0, 3.0, 0.3, 28.0, 0.2, 0.0, 1.0, 0.5],
        "Poulet":  [165.0, 31.0, 3.6, 0.0, 1.2, 0.0, 0.0, 1.0],
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


def _targets():
    return {
        "Calories": 600.0, "Protéines": 40.0, "Lipides": 12.0, "Glucides": 60.0,
        "Poids_Corps": 60.0, "Prix_Max": 20.0,
        "VitC": 100.0, "Fibres": 15.0, "Fer": 10.0,
    }


def test_returns_plan_score_and_ratio():
    plan, warning, score = optimize_ratio(_df(), _targets(), budget_max_daily=20.0, seed=3)
    assert plan is not None
    assert 0.0 <= score["couverture_moyenne"] <= 1.0
    assert score["cout_total"] > 0
    assert score["ratio"] == pytest.approx(
        score["equilibre_moyen"] / score["cout_total"], rel=1e-6)


def test_search_improves_ratio_after_floor_or_nutrition_before_floor():
    from app.services.sante.coverage import coverage_score
    from app.services.sante.optimizer import optimize_nutrition
    from app.services.sante.totals import calculate_plan_totals
    df, t = _df(), _targets()
    base_plan, _ = optimize_nutrition(df, t, budget_max_daily=20.0)
    base_tot = calculate_plan_totals(base_plan, df)
    base_cost = sum(it["Prix"] for it in base_plan)
    base_cov = coverage_score(base_tot, t)
    base_balance = base_cov["nutrition_balance_mean"]
    base_ratio = base_balance / base_cost
    _, _, score = optimize_ratio(df, t, budget_max_daily=20.0)
    if base_cov["coverage_mean"] >= 0.90:
        assert score["ratio"] >= base_ratio - 1e-9
    else:
        # Deux résolutions SLSQP peuvent différer de quelques dix-millionièmes
        # tout en représentant le même optimum numérique.
        assert score["equilibre_moyen"] >= base_balance - 1e-6


def test_optimize_ratio_forwards_pantry_quantities(monkeypatch):
    import app.services.sante.ratio_optimizer as ro
    seen = {}
    real = ro.optimize_nutrition

    def spy(df, targets, **kw):
        seen["pantry"] = kw.get("pantry_stock")
        return real(df, targets, **kw)

    monkeypatch.setattr(ro, "optimize_nutrition", spy)
    stock = {"Legume": [{"available_g": 500.0, "cost_factor": 0.5}]}
    optimize_ratio(_df(), _targets(), budget_max_daily=20.0, pantry_stock=stock)
    assert seen["pantry"] == stock


def test_adaptive_search_is_not_limited_to_six_solutions(monkeypatch):
    import app.services.sante.ratio_optimizer as ro

    calls = []
    real = ro.optimize_nutrition

    def spy(df, targets, **kw):
        calls.append((
            kw["price_weight"], kw["initial_seed"], kw["initial_quantities"]
        ))
        return real(df, targets, **kw)

    monkeypatch.setattr(ro, "optimize_nutrition", spy)
    optimize_ratio(
        _df(), _targets(), budget_max_daily=20.0,
        min_search_passes=8, max_search_passes=8, convergence_patience=2,
        price_weights=(0.001, 0.02, 0.08), refine=False,
    )
    assert len(calls) == 8
    assert len({initial_seed for _, initial_seed, _ in calls}) == 8
    assert calls[0][2] == {"Legume": 200.0, "Riz": 200.0, "Poulet": 200.0}
    assert all(initial is None for _, _, initial in calls[1:])


def test_progress_and_stop_keep_the_best_solution_found():
    updates = []
    plan, _, score = optimize_ratio(
        _df(), _targets(), budget_max_daily=20.0,
        min_search_passes=1, max_search_passes=20, convergence_patience=20,
        progress_cb=updates.append,
        should_stop=lambda: len(updates) >= 3,
        refine=False,
    )
    assert plan is not None
    assert 3 <= len(updates) < 20
    assert updates[-1]["temperature"] is not None
    assert updates[-1]["best_items"]
    assert {"aliment", "quantite_g"} <= set(updates[-1]["best_items"][0])
    assert score["stopped"] is True
    assert score["solutions_found"] >= 1


def test_continuous_mode_ignores_bound_and_stops_on_request():
    updates = []
    plan, _, score = optimize_ratio(
        _df(), _targets(), budget_max_daily=20.0,
        min_search_passes=1, max_search_passes=1, convergence_patience=1,
        progress_cb=updates.append,
        should_stop=lambda: len(updates) >= 3,
        continuous_until_stopped=True,
        refine=False,
    )
    assert plan is not None
    assert len(updates) >= 3  # dépasse bien max_search_passes=1
    assert updates[-1]["max_attempts"] is None
    assert score["stopped"] is True


def test_continuous_mode_simplifies_each_new_solution(monkeypatch):
    import app.services.sante.ratio_optimizer as ro

    prune_calls = []
    phases = []

    def fake_prune(plan, metrics, df, targets, **kwargs):
        prune_calls.append(True)
        callback = kwargs.get("progress_cb")
        simplified = [dict(item) for item in plan[:-1]]
        # Signature volontairement nouvelle : simule la compensation des
        # grammes de l'aliment retiré par ceux qui restent.
        simplified[0]["Quantite_g"] += 1.7
        improved = {
            **metrics,
            "ratio": metrics["ratio"] + 0.01,
            "equilibre_moyen": metrics.get("equilibre_moyen", 0.0) + 0.01,
        }
        removed = [plan[-1]["Aliment"]]
        if callback:
            callback({
                "phase": "simplification", "prune_attempt": 1,
                "prune_total": len(plan), "removed_foods": removed,
                "best_ratio": improved["ratio"],
                "best_coverage": improved.get("equilibre_moyen", 0.9),
                "best_cost": improved["cout_total"], "best_items": [],
            })
        return simplified, improved, removed

    monkeypatch.setattr(ro, "prune_redundant_foods", fake_prune)

    plan, _, score = optimize_ratio(
        _df(), _targets(), budget_max_daily=20.0,
        min_search_passes=1, max_search_passes=1, convergence_patience=99,
        progress_cb=lambda update: phases.append(update.get("phase", "search")),
        should_stop=lambda: bool(prune_calls),
        continuous_until_stopped=True,
        refine=True,
    )
    assert prune_calls
    assert "simplification" in phases
    assert score["stopped"] is True
    assert score["removed_foods"]
    assert plan is not None


def test_continuous_mode_also_simplifies_a_dominated_solution(monkeypatch):
    import app.services.sante.ratio_optimizer as ro

    first = [
        {"Aliment": "Legume", "Quantite_g": 120.0, "Prix": 0.48},
        {"Aliment": "Riz", "Quantite_g": 500.0, "Prix": 1.0},
        {"Aliment": "Poulet", "Quantite_g": 400.0, "Prix": 4.8},
    ]
    # Même score nutritionnel simulé, mais légèrement plus cher : ce deuxième
    # panier est dominé avant simplification et doit tout de même être testé.
    second = [dict(item) for item in first]
    second[0]["Quantite_g"] = 121.0
    second[0]["Prix"] = 0.484
    plans = iter([(first, ""), (second, "")])
    prune_calls = []
    updates = []

    monkeypatch.setattr(ro, "optimize_nutrition", lambda *args, **kwargs: next(plans))
    monkeypatch.setattr(
        ro, "coverage_score",
        lambda totals, targets: {
            "coverage_mean": 0.92,
            "nutrition_balance_mean": 0.92,
            "macro_balance_mean": 0.92,
            "pct_micros_atteints": 92.0,
            "sous_couverts": [],
        },
    )

    def fake_prune(plan, metrics, df, targets, **kwargs):
        prune_calls.append(tuple(item["Quantite_g"] for item in plan))
        callback = kwargs.get("progress_cb")
        if callback:
            callback({
                "phase": "simplification", "prune_attempt": 1,
                "prune_total": len(plan), "removed_foods": [],
                # Valeurs locales volontairement fausses : elles ne doivent
                # jamais remplacer le vrai meilleur dans la progression.
                "best_ratio": 999.0, "best_coverage": 1.0,
                "best_cost": 999.0, "best_items": [],
            })
        return plan, metrics, []

    monkeypatch.setattr(ro, "prune_redundant_foods", fake_prune)
    plan, _, score = optimize_ratio(
        _df(), _targets(), budget_max_daily=20.0,
        price_weights=(0.1,), min_search_passes=1, max_search_passes=1,
        progress_cb=updates.append,
        should_stop=lambda: len(prune_calls) >= 2,
        continuous_until_stopped=True, refine=True,
    )

    assert len(prune_calls) == 2
    assert prune_calls[1][0] == 121.0
    assert all(update.get("best_cost") != 999.0 for update in updates)
    assert score["stopped"] is True
    assert plan is not None


def test_best_ratio_can_beat_a_more_covered_but_much_costlier_plan(monkeypatch):
    import app.services.sante.ratio_optimizer as ro

    df = _df()
    df["PackagePrice"] = [20.0, 60.0, 20.0]
    df["PackageWeightG"] = 1000.0
    cheap = [
        {"Aliment": "Legume", "Quantite_g": 120.0, "Prix": 0.48},
        {"Aliment": "Poulet", "Quantite_g": 400.0, "Prix": 4.8},
    ]
    expensive = [
        {"Aliment": "Legume", "Quantite_g": 125.0, "Prix": 0.5},
        {"Aliment": "Riz", "Quantite_g": 500.0, "Prix": 1.0},
        {"Aliment": "Poulet", "Quantite_g": 400.0, "Prix": 4.8},
    ]
    plans = iter([(cheap, ""), (expensive, "")])
    monkeypatch.setattr(ro, "optimize_nutrition", lambda *a, **k: next(plans))
    monkeypatch.setattr(
        ro, "coverage_score",
        lambda totals, targets: {
            "coverage_mean": 0.92 if totals["Glucides"] < 100 else 0.99,
            "pct_micros_atteints": 92.0 if totals["Glucides"] < 100 else 99.0,
            "sous_couverts": [],
        },
    )
    plan, _, score = optimize_ratio(
        df, _targets(), budget_max_daily=1000,
        price_weights=(0.1, 0.2), min_search_passes=2, max_search_passes=2,
        refine=False,
    )
    assert plan == cheap
    assert score["couverture_moyenne"] == 0.92


def test_below_nutrition_floor_search_prefers_closest_to_floor(monkeypatch):
    import app.services.sante.ratio_optimizer as ro

    df = _df()
    cheap_weak = [
        {"Aliment": "Riz", "Quantite_g": 500.0, "Prix": 1.0},
        {"Aliment": "Poulet", "Quantite_g": 200.0, "Prix": 2.4},
    ]
    better = [
        {"Aliment": "Legume", "Quantite_g": 300.0, "Prix": 1.2},
        {"Aliment": "Riz", "Quantite_g": 500.0, "Prix": 1.0},
        {"Aliment": "Poulet", "Quantite_g": 200.0, "Prix": 2.4},
    ]
    plans = iter([(cheap_weak, ""), (better, "")])
    monkeypatch.setattr(ro, "optimize_nutrition", lambda *a, **k: next(plans))
    monkeypatch.setattr(
        ro, "coverage_score",
        lambda totals, targets: {
            "coverage_mean": 0.70 if totals["VitC"] < 100 else 0.85,
            "nutrition_balance_mean": 0.72 if totals["VitC"] < 100 else 0.86,
            "macro_balance_mean": 0.74 if totals["VitC"] < 100 else 0.87,
            "pct_micros_atteints": 70.0 if totals["VitC"] < 100 else 85.0,
            "sous_couverts": [],
        },
    )
    plan, _, score = optimize_ratio(
        df, _targets(), budget_max_daily=1000,
        price_weights=(0.1, 0.2), min_search_passes=2, max_search_passes=2,
        refine=False,
    )
    assert plan == better
    assert score["equilibre_moyen"] == 0.86


def test_pruning_tries_most_expensive_per_kg_first_and_never_adds_a_food(monkeypatch):
    import app.services.sante.ratio_optimizer as ro

    df = _df()
    initial = [
        {"Aliment": "Legume", "Quantite_g": 5.0, "Prix": 0.02},
        {"Aliment": "Riz", "Quantite_g": 200.0, "Prix": 0.4},
        {"Aliment": "Poulet", "Quantite_g": 300.0, "Prix": 3.6},
    ]
    seen_subsets = []

    def fake_optimize(subset, targets, **kwargs):
        seen_subsets.append(list(subset.index))
        return [
            {"Aliment": name, "Quantite_g": kwargs["initial_quantities"][name],
             "Prix": float(subset.loc[name, "Prix"])}
            for name in subset.index
        ], ""

    monkeypatch.setattr(ro, "optimize_nutrition", fake_optimize)
    monkeypatch.setattr(
        ro, "_plan_metrics",
        lambda plan, subset, targets, pantry_stock=None: {
            "couverture_moyenne": 0.91,
            "pct_micros_atteints": 91.0,
            "cout_total": 3.0,
            "ratio": 0.31,
            "sous_couverts": [],
        },
    )
    plan, metrics, removed = ro.prune_redundant_foods(
        initial,
        {"couverture_moyenne": 0.90, "cout_total": 4.02, "ratio": 0.20},
        df, _targets(), price_weight=0.1,
    )

    # Poulet (1,20 $/100 g) est testé avant légume (0,40) et riz (0,20).
    assert seen_subsets[0] == ["Legume", "Riz"]
    assert all(set(subset) <= {"Legume", "Riz", "Poulet"} for subset in seen_subsets)
    assert "Poulet" in removed
    assert all(item["Aliment"] != "Poulet" for item in plan)
    assert metrics["ratio"] == 0.31


def test_economic_cost_values_stock_at_half_then_surplus_at_full_price():
    import app.services.sante.ratio_optimizer as ro

    df = _df()
    plan = [{"Aliment": "Legume", "Quantite_g": 600.0, "Prix": 2.4}]
    stock = {"Legume": [{"available_g": 500.0, "cost_factor": 0.5}]}
    # 500 g × 0.40 CAD/100 g × 50 %, then 100 g at full price.
    assert ro._purchase_cost(plan, df, stock) == pytest.approx(1.4)
    assert ro._cash_purchase_cost(plan, df, stock) == pytest.approx(0.4)


def test_package_checkout_only_charges_the_uncovered_stock_deficit():
    import app.services.sante.ratio_optimizer as ro

    df = _df()
    df["PackagePrice"] = [20.0, 60.0, 20.0]
    df["PackageWeightG"] = 1000.0
    plan = [{"Aliment": "Legume", "Quantite_g": 600.0, "Prix": 2.4}]
    stock = {"Legume": [{"available_g": 500.0, "cost_factor": 0.5}]}
    assert ro._purchase_cost(plan, df, stock) == pytest.approx(1.4)
    # A 100 g deficit still requires buying the 1 kg pack at checkout.
    assert ro._cash_purchase_cost(plan, df, stock) == pytest.approx(20.0)


def test_fully_covered_perishable_plan_has_finite_ratio():
    import app.services.sante.ratio_optimizer as ro

    df = _df()
    plan = [{"Aliment": "Poulet", "Quantite_g": 400.0, "Prix": 4.8}]
    stock = {"Poulet": [{"available_g": 400.0, "cost_factor": 0.0}]}
    metrics = ro._plan_metrics(plan, df, _targets(), stock)
    assert metrics is not None
    assert metrics["cout_total"] == pytest.approx(0.0)
    assert metrics["ratio"] > 0.0
    assert metrics["ratio"] < float("inf")
