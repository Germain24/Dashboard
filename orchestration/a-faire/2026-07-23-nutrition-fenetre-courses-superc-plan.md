# Fenêtre nutrition batch-cook → liste de courses Super C — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entrer son poids lun/jeu génère un plan nutrition sur la fenêtre batch-cook (3 ou 4 jours), une liste de courses Super C agrégée à cocher, et un score couverture-micro/coût maximisé, avec report escaladé des manques d'une fenêtre à l'autre.

**Architecture :** On réutilise l'optimiseur SLSQP par-jour existant (`optimize_nutrition`) en lui donnant des cibles **fenêtre** (somme des jours). Le « ratio pur » couverture/coût est réalisé par un **balayage borné du poids-prix** qui sélectionne la solution au meilleur vrai ratio (chemin simple sanctionné par la spec §2, retenu pour sa robustesse/testabilité vs. Dinkelbach). Un module de **dette** escalade la priorité d'un micro chroniquement sous-consommé. La couche persistance = une table `WindowPlan` + les lignes `PlanNutrition` par jour existantes.

**Tech Stack :** Python 3 / FastAPI / SQLModel / SQLite (Alembic) / SciPy SLSQP / pandas / numpy. Frontend Next.js + React Query + Tailwind (tokens `var(--...)`).

## Global Constraints

- Spec de référence : `orchestration/a-faire/2026-07-22-nutrition-fenetre-courses-superc-design.md`. **Sous-projet A uniquement** ; le panier Instacart auto (B) est hors scope.
- Cadence en dur : **lundi (weekday 0) → 3 jours** [lun, mar, mer] ; **jeudi (weekday 3) → 4 jours** [jeu, ven, sam, dim].
- Les macros restent des **contraintes** (calories & protéines ≥ cible fenêtre ; budget ≤ plafond). Le score (couverture micro / coût) est l'objectif.
- Report des manques = **consommation réelle** loggée (champ `PlanNutrition.consumed`), micros uniquement.
- Micros à atteindre (numérateur du score) = les 22 clés métier : `Fibres, Magnésium, Omega3, VitA, VitB1, VitB2, VitB3, VitB5, VitB6, VitB9, VitB12, VitC, VitD, VitE, VitK, Calcium, Fer, Zinc, Potassium, Iode, Sélénium, Phosphore`.
- **Best-effort prix** : tout échec de scrape/tarification Super C ne casse jamais la génération (prix de repli du catalogue).
- Tout nouveau modèle SQLModel doit être importé dans `backend/app/models/__init__.py` **et** accompagné d'une migration Alembic (sinon `backend/tests/test_migrations.py` échoue).
- Tests : `pytest` depuis `backend/`, fichiers sous `backend/tests/test_sante/` (fonctions pures testées directement ; API via `TestClient` + `SQLModel.metadata.create_all`). Style FR, comme l'existant.
- Commits fréquents, un par tâche (message FR, préfixe conventionnel, trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`).

---

## Phase 1 — Moteur pur (aucune DB)

### Task 1 : `optimize_nutrition` accepte un poids-prix et un multiplicateur de priorité micro

**Files:**
- Modify: `backend/app/services/sante/optimizer.py`
- Test: `backend/tests/test_sante/test_optimizer_params.py`

**Interfaces:**
- Produces: `optimize_nutrition(df, targets, budget_max_daily=None, seed=None, price_weight=0.001, micro_weight_mult=None) -> tuple[list[dict]|None, str]`. `price_weight` remplace le coefficient prix codé en dur `0.001`. `micro_weight_mult: dict[str,float]|None` mappe une **clé métier micro** (ex. `"VitD"`) → facteur multipliant sa pénalité de couverture (via `NUTRIENT_KEY_TO_CSV`). Défauts = comportement actuel inchangé.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_optimizer_params.py
import numpy as np
import pandas as pd
import pytest

from app.services.sante.optimizer import optimize_nutrition


def _mini_df():
    """Deux aliments : 'Cher' riche en VitD mais coûteux, 'Pas cher' générique."""
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitD", "Fibres"]
    data = {
        "Cher":      [100.0, 8.0, 2.0, 10.0, 5.0, 40.0, 2.0],
        "Pas cher":  [100.0, 8.0, 2.0, 10.0, 0.5, 0.0, 2.0],
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


def _targets():
    return {
        "Calories": 300.0, "Protéines": 20.0, "Lipides": 6.0, "Glucides": 30.0,
        "Poids_Corps": 60.0, "Prix_Max": 30.0,
        "VitD": 15.0, "Fibres": 10.0,
    }


def test_default_price_weight_preserves_behaviour():
    df, t = _mini_df(), _targets()
    plan_a, _ = optimize_nutrition(df, t, budget_max_daily=30.0, seed=1)
    plan_b, _ = optimize_nutrition(df, t, budget_max_daily=30.0, seed=1, price_weight=0.001)
    grams = lambda p: {it["Aliment"]: round(it["Quantite_g"], 3) for it in p}
    assert grams(plan_a) == grams(plan_b)


def test_higher_price_weight_shifts_toward_cheaper_food():
    df, t = _mini_df(), _targets()
    cheap = lambda p: sum(it["Quantite_g"] for it in p if it["Aliment"] == "Pas cher")
    low = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=0.001)[0]
    high = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=2.0)[0]
    assert cheap(high) >= cheap(low)


def test_micro_weight_mult_forces_expensive_micro():
    df, t = _mini_df(), _targets()
    vitd = lambda p: sum(it["Quantite_g"] for it in p if it["Aliment"] == "Cher")
    base = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=1.0)[0]
    forced = optimize_nutrition(df, t, budget_max_daily=30.0, price_weight=1.0,
                                micro_weight_mult={"VitD": 8.0})[0]
    assert vitd(forced) > vitd(base)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_optimizer_params.py -v`
Expected: FAIL — `optimize_nutrition() got an unexpected keyword argument 'price_weight'`.

- [ ] **Step 3: Add the two parameters and wire them into the objective**

Dans `backend/app/services/sante/optimizer.py` :

1. Signature (remplacer) :
```python
def optimize_nutrition(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float] = None,
    seed: Optional[int] = None,
    price_weight: float = 0.001,
    micro_weight_mult: Optional[dict[str, float]] = None,
) -> tuple[list[dict[str, Any]] | None, str]:
```

2. Juste après le calcul de `nutrient_targets`, construire le multiplicateur par colonne CSV :
```python
    from app.services.sante.constants import NUTRIENT_KEY_TO_CSV
    mult_by_col: dict[str, float] = {}
    for key, factor in (micro_weight_mult or {}).items():
        col = NUTRIENT_KEY_TO_CSV.get(key)
        if col is not None:
            mult_by_col[col] = float(factor)
```

3. Dans `objective`, la branche couverture (le `else` où `error += COVERAGE_WEIGHT * (shortfall ** COVERAGE_POWER)`), appliquer le multiplicateur :
```python
            else:
                shortfall = -rel_error if rel_error < 0.0 else 0.0
                cov_w = COVERAGE_WEIGHT * mult_by_col.get(csv_col, 1.0)
                error += cov_w * (shortfall ** COVERAGE_POWER)
                if rel_error > 1.0:
                    error += 5.0 * ((rel_error - 1.0) ** 2)
```

4. Remplacer la pénalité prix codée en dur :
```python
        # Pénalité prix pilotée par price_weight (balayage du ratio, cf. ratio_optimizer)
        error += price_weight * float(np.dot(x, prix_arr))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_optimizer_params.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Guard against regressions in the existing optimizer test**

Run: `cd backend && python -m pytest tests/test_sante/ -q`
Expected: PASS (aucune régression sur les tests optimiseur existants).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sante/optimizer.py backend/tests/test_sante/test_optimizer_params.py
git commit -m "feat(sante): optimize_nutrition prend price_weight + micro_weight_mult (fenetre §2)"
```

---

### Task 2 : Logique de fenêtre pure (`fenetre.py`)

**Files:**
- Create: `backend/app/services/sante/fenetre.py`
- Test: `backend/tests/test_sante/test_fenetre.py`

**Interfaces:**
- Produces:
  - `anchor_for(day: dt.date) -> dt.date` — l'ancre (lun ou jeu) de la fenêtre contenant `day`.
  - `window_days(anchor: dt.date) -> list[dt.date]` — [3 jours] si lun, [4 jours] si jeu, sinon `ValueError`.
  - `window_targets(daily: list[dict[str, float]]) -> dict[str, float]` — somme clé-à-clé de toutes les cibles journalières.
  - `split_by_day(food_set: dict[str, float], calorie_targets: list[float]) -> list[dict[str, float]]` — grammes par jour au prorata des calories-cibles (Σ jours = food_set).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_fenetre.py
import datetime as dt
import pytest

from app.services.sante import fenetre


def test_anchor_for_monday_window():
    # mar 2026-07-21 → ancre lundi 2026-07-20
    assert fenetre.anchor_for(dt.date(2026, 7, 21)) == dt.date(2026, 7, 20)


def test_anchor_for_thursday_window():
    # dim 2026-07-26 → ancre jeudi 2026-07-23
    assert fenetre.anchor_for(dt.date(2026, 7, 26)) == dt.date(2026, 7, 23)


def test_window_days_lengths():
    assert fenetre.window_days(dt.date(2026, 7, 20)) == [
        dt.date(2026, 7, 20), dt.date(2026, 7, 21), dt.date(2026, 7, 22)]
    assert fenetre.window_days(dt.date(2026, 7, 23)) == [
        dt.date(2026, 7, 23), dt.date(2026, 7, 24),
        dt.date(2026, 7, 25), dt.date(2026, 7, 26)]


def test_window_days_rejects_non_anchor():
    with pytest.raises(ValueError):
        fenetre.window_days(dt.date(2026, 7, 21))  # mardi


def test_window_targets_sums_keys():
    daily = [
        {"Calories": 2000.0, "VitC": 100.0, "Prix_Max": 18.0},
        {"Calories": 1800.0, "VitC": 100.0, "Prix_Max": 18.0},
    ]
    out = fenetre.window_targets(daily)
    assert out["Calories"] == pytest.approx(3800.0)
    assert out["VitC"] == pytest.approx(200.0)
    assert out["Prix_Max"] == pytest.approx(36.0)


def test_split_by_day_proportional_and_conserving():
    food = {"Riz": 900.0, "Poulet": 300.0}
    per_day = fenetre.split_by_day(food, [2000.0, 1000.0])  # 2:1
    assert per_day[0]["Riz"] == pytest.approx(600.0)
    assert per_day[1]["Riz"] == pytest.approx(300.0)
    # conservation : la somme des jours = le total
    assert sum(d["Riz"] for d in per_day) == pytest.approx(900.0)
    assert sum(d["Poulet"] for d in per_day) == pytest.approx(300.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.sante.fenetre'`.

- [ ] **Step 3: Implement `fenetre.py`**

```python
# backend/app/services/sante/fenetre.py
"""Logique pure de la fenêtre batch-cook (cadence, cibles, répartition).

Cadence figée (spec §1) : lundi → 3 jours [lun,mar,mer] ; jeudi → 4 jours
[jeu,ven,sam,dim]. Les autres jours appartiennent à l'une de ces deux fenêtres.
"""
from __future__ import annotations

import datetime as dt

_MONDAY, _THURSDAY = 0, 3


def anchor_for(day: dt.date) -> dt.date:
    """Ancre (lun ou jeu) de la fenêtre contenant `day`."""
    wd = day.weekday()
    if wd in (0, 1, 2):
        return day - dt.timedelta(days=wd)          # → lundi
    return day - dt.timedelta(days=wd - _THURSDAY)  # jeu..dim → jeudi


def window_days(anchor: dt.date) -> list[dt.date]:
    """Jours couverts par une fenêtre ancrée lun (3) ou jeu (4)."""
    wd = anchor.weekday()
    if wd == _MONDAY:
        n = 3
    elif wd == _THURSDAY:
        n = 4
    else:
        raise ValueError(f"Ancre invalide {anchor} (weekday={wd}) : attendu lundi ou jeudi.")
    return [anchor + dt.timedelta(days=i) for i in range(n)]


def window_targets(daily: list[dict[str, float]]) -> dict[str, float]:
    """Somme clé-à-clé des cibles journalières (Calories, micros, Prix_Max,
    Poids_Corps… tout est additif : la fenêtre vise le total des jours)."""
    out: dict[str, float] = {}
    for d in daily:
        for k, v in d.items():
            try:
                out[k] = out.get(k, 0.0) + float(v)
            except (TypeError, ValueError):
                continue
    return out


def split_by_day(
    food_set: dict[str, float], calorie_targets: list[float]
) -> list[dict[str, float]]:
    """Répartit les grammes totaux par jour au prorata des calories-cibles.

    Σ (jours) = food_set exactement (le dernier jour absorbe l'arrondi flottant).
    """
    total_cal = sum(calorie_targets)
    n = len(calorie_targets)
    if n == 0 or total_cal <= 0:
        return [dict(food_set)] if n <= 1 else [{} for _ in range(n)]
    shares = [c / total_cal for c in calorie_targets]
    per_day: list[dict[str, float]] = [{} for _ in range(n)]
    for aliment, grams in food_set.items():
        assigned = 0.0
        for i in range(n - 1):
            g = grams * shares[i]
            per_day[i][aliment] = g
            assigned += g
        per_day[n - 1][aliment] = grams - assigned  # reste exact
    return per_day
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sante/fenetre.py backend/tests/test_sante/test_fenetre.py
git commit -m "feat(sante): logique pure de fenetre batch-cook (cadence, cibles, repartition)"
```

---

### Task 3 : Score de couverture micro (`coverage.py`)

**Files:**
- Create: `backend/app/services/sante/coverage.py`
- Test: `backend/tests/test_sante/test_coverage.py`

**Interfaces:**
- Produces:
  - `MICRO_KEYS: list[str]` — les 22 clés métier à atteindre.
  - `coverage_score(totals: dict[str, float], targets: dict[str, float]) -> dict` → `{"coverage_mean": float(0..1), "pct_micros_atteints": float(0..100), "n_micros": int, "sous_couverts": list[str]}`. `sous_couverts` = micros avec apport < cible, triés par couverture croissante.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_coverage.py
import pytest
from app.services.sante.coverage import MICRO_KEYS, coverage_score


def test_full_coverage():
    targets = {k: 10.0 for k in MICRO_KEYS}
    totals = {k: 12.0 for k in MICRO_KEYS}  # tout dépassé
    out = coverage_score(totals, targets)
    assert out["coverage_mean"] == pytest.approx(1.0)
    assert out["pct_micros_atteints"] == pytest.approx(100.0)
    assert out["sous_couverts"] == []


def test_capped_and_shortfall():
    targets = {"VitC": 100.0, "Fer": 10.0}
    totals = {"VitC": 200.0, "Fer": 5.0}  # VitC capé à 1.0, Fer à 0.5
    out = coverage_score(totals, targets)
    assert out["coverage_mean"] == pytest.approx(0.75)
    assert out["pct_micros_atteints"] == pytest.approx(50.0)
    assert out["sous_couverts"] == ["Fer"]


def test_missing_target_key_ignored():
    out = coverage_score({"VitC": 50.0}, {"VitC": 100.0})
    assert out["n_micros"] == 1
    assert out["coverage_mean"] == pytest.approx(0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_coverage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.sante.coverage'`.

- [ ] **Step 3: Implement `coverage.py`**

```python
# backend/app/services/sante/coverage.py
"""Score de couverture micronutritionnelle = numérateur du ratio (spec §2).

coverage_mean = moyenne, sur les micros à atteindre, de min(apport/cible, 1).
"""
from __future__ import annotations

MICRO_KEYS: list[str] = [
    "Fibres", "Magnésium", "Omega3",
    "VitA", "VitB1", "VitB2", "VitB3", "VitB5", "VitB6", "VitB9", "VitB12",
    "VitC", "VitD", "VitE", "VitK",
    "Calcium", "Fer", "Zinc", "Potassium", "Iode", "Sélénium", "Phosphore",
]


def coverage_score(totals: dict[str, float], targets: dict[str, float]) -> dict:
    """Couverture moyenne (0..1), % de micros pleinement atteints, sous-couverts."""
    covs: list[tuple[str, float]] = []
    met = 0
    for k in MICRO_KEYS:
        tgt = targets.get(k)
        if not tgt or float(tgt) <= 0:
            continue
        got = float(totals.get(k, 0.0) or 0.0)
        cov = min(got / float(tgt), 1.0)
        covs.append((k, cov))
        if got >= float(tgt):
            met += 1
    n = len(covs)
    if n == 0:
        return {"coverage_mean": 0.0, "pct_micros_atteints": 0.0,
                "n_micros": 0, "sous_couverts": []}
    coverage_mean = sum(c for _, c in covs) / n
    sous = [k for k, c in sorted(covs, key=lambda kc: kc[1]) if c < 1.0]
    return {
        "coverage_mean": coverage_mean,
        "pct_micros_atteints": met / n * 100.0,
        "n_micros": n,
        "sous_couverts": sous,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_coverage.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sante/coverage.py backend/tests/test_sante/test_coverage.py
git commit -m "feat(sante): score de couverture micro (numerateur du ratio)"
```

---

### Task 4 : Optimiseur de ratio par balayage du poids-prix (`ratio_optimizer.py`)

**Files:**
- Create: `backend/app/services/sante/ratio_optimizer.py`
- Test: `backend/tests/test_sante/test_ratio_optimizer.py`

**Interfaces:**
- Consumes: `optimize_nutrition(..., price_weight, micro_weight_mult)` (Task 1) ; `calculate_plan_totals` ; `coverage_score` (Task 3).
- Produces: `optimize_ratio(df, targets, budget_max_daily=None, seed=None, micro_weight_mult=None, price_weights=DEFAULT_PRICE_WEIGHTS) -> tuple[list[dict]|None, str, dict]`. Renvoie `(plan, warning, score)` du **meilleur vrai ratio** couverture/coût observé sur le balayage. `score = {couverture_moyenne, pct_micros_atteints, cout_total, ratio, sous_couverts}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_ratio_optimizer.py
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
        score["couverture_moyenne"] / score["cout_total"], rel=1e-6)


def test_ratio_at_least_as_good_as_single_default_pass():
    from app.services.sante.optimizer import optimize_nutrition
    from app.services.sante.totals import calculate_plan_totals
    from app.services.sante.coverage import coverage_score
    df, t = _df(), _targets()
    base_plan, _ = optimize_nutrition(df, t, budget_max_daily=20.0)
    base_tot = calculate_plan_totals(base_plan, df)
    base_cost = sum(it["Prix"] for it in base_plan)
    base_ratio = coverage_score(base_tot, t)["coverage_mean"] / base_cost
    _, _, score = optimize_ratio(df, t, budget_max_daily=20.0)
    assert score["ratio"] >= base_ratio - 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_ratio_optimizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.sante.ratio_optimizer'`.

- [ ] **Step 3: Implement `ratio_optimizer.py`**

```python
# backend/app/services/sante/ratio_optimizer.py
"""Maximise le ratio couverture-micro / coût (spec §2) par balayage borné du
poids-prix passé à l'optimiseur SLSQP, en sélectionnant la solution au meilleur
VRAI ratio. Robuste : réutilise entièrement `optimize_nutrition` (contraintes,
bornes, snap MinQty) sans en réécrire la physique.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.services.sante.coverage import coverage_score
from app.services.sante.optimizer import optimize_nutrition
from app.services.sante.totals import calculate_plan_totals

# Du plus permissif (couverture max, prix ~ignoré) au plus avare : on cherche le
# point où couverture/coût est maximal.
DEFAULT_PRICE_WEIGHTS: tuple[float, ...] = (0.001, 0.02, 0.08, 0.25, 0.6, 1.2)


def optimize_ratio(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float] = None,
    seed: Optional[int] = None,
    micro_weight_mult: Optional[dict[str, float]] = None,
    price_weights: tuple[float, ...] = DEFAULT_PRICE_WEIGHTS,
) -> tuple[list[dict[str, Any]] | None, str, dict]:
    best: tuple[list[dict], str, dict] | None = None
    best_ratio = -1.0
    last_warning = ""
    for pw in price_weights:
        plan, warning = optimize_nutrition(
            df, targets, budget_max_daily=budget_max_daily, seed=seed,
            price_weight=pw, micro_weight_mult=micro_weight_mult,
        )
        last_warning = warning
        if plan is None:
            continue
        totals = calculate_plan_totals(plan, df)
        cost = float(sum(it["Prix"] for it in plan))
        cov = coverage_score(totals, targets)
        ratio = cov["coverage_mean"] / cost if cost > 0 else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best = (plan, warning, {
                "couverture_moyenne": cov["coverage_mean"],
                "pct_micros_atteints": cov["pct_micros_atteints"],
                "cout_total": cost,
                "ratio": ratio,
                "sous_couverts": cov["sous_couverts"],
            })
    if best is None:
        return None, (last_warning or "Optimisation impossible sur tout le balayage."), {}
    return best
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_ratio_optimizer.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sante/ratio_optimizer.py backend/tests/test_sante/test_ratio_optimizer.py
git commit -m "feat(sante): optimiseur de ratio couverture/cout par balayage du poids-prix"
```

---

### Task 5 : Report + escalade de priorité sur la dette micro (`debt.py`)

**Files:**
- Create: `backend/app/services/sante/debt.py`
- Test: `backend/tests/test_sante/test_debt.py`

**Interfaces:**
- Consumes: `MICRO_KEYS` (Task 3).
- Produces: `carryover(prev_targets: dict, prev_consumed: dict, prev_series: dict|None) -> tuple[dict, dict, dict]` → `(target_add, weight_mult, new_series)`. `target_add[micro]` = grammes/µg à ajouter à la cible fenêtre (dette reportée, bornée) ; `weight_mult[micro]` = facteur de priorité pour `optimize_nutrition(micro_weight_mult=...)` ; `new_series[micro]` = compteur de fenêtres consécutives en déficit. Micros uniquement ; un surplus remet la série à 0 sans créditer (report conservateur).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_debt.py
import pytest
from app.services.sante.debt import ESCALATION, MAX_MULT, carryover


def test_deficit_reports_and_escalates():
    prev_t = {"VitD": 30.0}
    prev_c = {"VitD": 10.0}                 # déficit 20
    add, mult, series = carryover(prev_t, prev_c, {"VitD": 2})
    assert add["VitD"] > 0
    assert series["VitD"] == 3              # 2 → 3
    assert mult["VitD"] == pytest.approx(min(ESCALATION ** 3, MAX_MULT))


def test_surplus_resets_series_no_credit():
    add, mult, series = carryover({"VitC": 100.0}, {"VitC": 150.0}, {"VitC": 4})
    assert series["VitC"] == 0
    assert "VitC" not in add                # pas de crédit
    assert mult.get("VitC", 1.0) == 1.0


def test_report_is_bounded():
    # déficit énorme : le report ne dépasse pas 50 % de la cible
    add, _, _ = carryover({"Fer": 10.0}, {"Fer": 0.0}, None)
    assert add["Fer"] == pytest.approx(5.0)


def test_ignores_non_micro_keys():
    add, mult, series = carryover({"Calories": 3000.0}, {"Calories": 1000.0}, None)
    assert "Calories" not in add and "Calories" not in mult and "Calories" not in series
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_debt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.sante.debt'`.

- [ ] **Step 3: Implement `debt.py`**

```python
# backend/app/services/sante/debt.py
"""Report + escalade de priorité de la dette micronutritionnelle (spec §3).

Basé sur la consommation RÉELLE de la fenêtre précédente. Un micro sous-consommé
voit sa cible relevée (borné) et sa priorité escaladée ; escaladée assez de
fenêtres, elle force l'optimiseur à le couvrir malgré le coût (contrepoids du
ratio pur). Un surplus remet la série à 0 sans créditer (report conservateur :
on ne « banque » pas un excès, surtout hydrosoluble).
"""
from __future__ import annotations

from app.services.sante.coverage import MICRO_KEYS

ESCALATION = 1.6          # facteur multiplicatif de priorité par fenêtre de dette
MAX_MULT = 8.0            # plafond de priorité (évite de tout sacrifier à un micro)
REPORT_FRACTION = 0.5    # report borné à 50 % de la cible de la fenêtre passée


def carryover(
    prev_targets: dict[str, float],
    prev_consumed: dict[str, float],
    prev_series: dict[str, int] | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    prev_series = prev_series or {}
    target_add: dict[str, float] = {}
    weight_mult: dict[str, float] = {}
    new_series: dict[str, int] = {}
    for m in MICRO_KEYS:
        tgt = prev_targets.get(m)
        if not tgt or float(tgt) <= 0:
            continue
        tgt = float(tgt)
        got = float(prev_consumed.get(m, 0.0) or 0.0)
        gap = tgt - got
        if gap > 0:                                   # déficit
            streak = int(prev_series.get(m, 0)) + 1
            new_series[m] = streak
            target_add[m] = min(gap, tgt * REPORT_FRACTION)
            weight_mult[m] = min(ESCALATION ** streak, MAX_MULT)
        else:                                         # atteint ou surplus
            new_series[m] = 0
    return target_add, weight_mult, new_series
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_debt.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sante/debt.py backend/tests/test_sante/test_debt.py
git commit -m "feat(sante): report + escalade de priorite de la dette micro (conso reelle)"
```

---

## Phase 2 — Persistance, service, API, scheduler

### Task 6 : Modèle `WindowPlan` + migration Alembic

**Files:**
- Modify: `backend/app/models/sante.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<hash>_window_plan.py` (autogénéré)
- Test: `backend/tests/test_sante/test_window_plan_model.py`

**Interfaces:**
- Produces: `WindowPlan(SQLModel, table=True)` avec `anchor_date: dt.date (unique, index)`, `length: int`, `poids_used: float|None`, `food_set: dict (JSON)`, `shopping_list: list (JSON)`, `score: dict (JSON)`, `debt_series: dict (JSON)`, `warning: str|None`, `created_at: dt.datetime`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_window_plan_model.py
import datetime as dt
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401  (enregistre les tables)
from app.models.sante import WindowPlan


def test_window_plan_roundtrip():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(WindowPlan(
            anchor_date=dt.date(2026, 7, 20), length=3, poids_used=51.0,
            food_set={"Riz": 900.0}, shopping_list=[{"aliment": "Riz", "quantite_g": 900.0}],
            score={"ratio": 0.02}, debt_series={"VitD": 1},
        ))
        s.commit()
        row = s.exec(select(WindowPlan).where(WindowPlan.anchor_date == dt.date(2026, 7, 20))).one()
        assert row.length == 3
        assert row.food_set["Riz"] == 900.0
        assert row.debt_series["VitD"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_window_plan_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'WindowPlan'`.

- [ ] **Step 3: Add the model**

Dans `backend/app/models/sante.py`, après `PlanNutrition` :
```python
class WindowPlan(SQLModel, table=True):
    """Plan d'une fenêtre batch-cook (spec §5) : jeu d'aliments commun, liste de
    courses agrégée, score, dette. Les portions par jour vivent dans PlanNutrition."""

    __tablename__ = "window_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    anchor_date: dt.date = Field(index=True, unique=True)
    length: int
    poids_used: Optional[float] = None
    food_set: dict = Field(default_factory=dict, sa_column=Column(JSON))
    shopping_list: list = Field(default_factory=list, sa_column=Column(JSON))
    score: dict = Field(default_factory=dict, sa_column=Column(JSON))
    debt_series: dict = Field(default_factory=dict, sa_column=Column(JSON))
    warning: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=utcnow)
```

Dans `backend/app/models/__init__.py`, remplacer la ligne d'import sante par :
```python
from app.models.sante import Aliment, MesureSante, NutritionGoal, PlanNutrition, WindowPlan  # noqa: F401
```

- [ ] **Step 4: Run the model test (passes) then generate the migration**

Run: `cd backend && python -m pytest tests/test_sante/test_window_plan_model.py -v`
Expected: PASS.

Run: `cd backend && alembic revision --autogenerate -m "window_plan"`
Expected: crée `backend/alembic/versions/<hash>_window_plan.py`. Ouvrir le fichier et vérifier qu'`upgrade()` contient `op.create_table("window_plan", ...)` avec les colonnes ci-dessus et `downgrade()` un `op.drop_table("window_plan")`. Si l'autogénération capte d'autres diffs parasites, ne garder que la création/suppression de `window_plan`.

- [ ] **Step 5: Verify the metadata/migration consistency test passes**

Run: `cd backend && python -m pytest tests/test_migrations.py -q`
Expected: PASS (le schéma des modèles == migrations ; sinon ajuster la révision).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/sante.py backend/app/models/__init__.py backend/alembic/versions/ backend/tests/test_sante/test_window_plan_model.py
git commit -m "feat(sante): modele WindowPlan + migration (persistance fenetre)"
```

---

### Task 7 : Schémas API de la fenêtre

**Files:**
- Modify: `backend/app/api/sante/schemas.py`
- Test: `backend/tests/test_sante/test_fenetre_schemas.py`

**Interfaces:**
- Produces (Pydantic) :
  - `FenetreGenerateRequest { date: dt.date|None, poids: float|None, force: bool=False }`
  - `ShoppingItem { aliment: str, quantite_g: float, prix: float|None, promo: bool=False }`
  - `FenetreDayPlan { date: dt.date, intensite: str, items: list[PlanItem], totals: dict[str,float] }`
  - `FenetreScore { couverture_moyenne: float, pct_micros_atteints: float, cout_total: float, ratio: float, sous_couverts: list[str] }`
  - `WindowPlanResponse { anchor_date, length, poids_used, jours: list[FenetreDayPlan], shopping_list: list[ShoppingItem], score: FenetreScore, warning: str|None }`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_fenetre_schemas.py
import datetime as dt
from app.api.sante.schemas import (
    FenetreGenerateRequest, FenetreScore, ShoppingItem, WindowPlanResponse,
)


def test_schemas_construct():
    req = FenetreGenerateRequest(date=dt.date(2026, 7, 20))
    assert req.force is False
    resp = WindowPlanResponse(
        anchor_date=dt.date(2026, 7, 20), length=3, poids_used=51.0, jours=[],
        shopping_list=[ShoppingItem(aliment="Riz", quantite_g=900.0, prix=1.8, promo=True)],
        score=FenetreScore(couverture_moyenne=0.8, pct_micros_atteints=70.0,
                           cout_total=42.0, ratio=0.019, sous_couverts=["VitD"]),
        warning=None,
    )
    assert resp.shopping_list[0].promo is True
    assert resp.score.sous_couverts == ["VitD"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'FenetreGenerateRequest'`.

- [ ] **Step 3: Add the schemas**

À la fin de `backend/app/api/sante/schemas.py` :
```python
# ─────────────────────────────────────────────────────────────────────────────
# Fenêtre batch-cook
# ─────────────────────────────────────────────────────────────────────────────

class FenetreGenerateRequest(BaseModel):
    date: Optional[dt.date] = Field(default=None, description="Un jour de la fenêtre (défaut : aujourd'hui). L'ancre lun/jeu en est dérivée.")
    poids: Optional[float] = Field(default=None, description="Poids ; si absent, dernière MesureSante.")
    force: bool = Field(default=False, description="Régénère (seed aléatoire) même si la fenêtre existe.")


class ShoppingItem(BaseModel):
    aliment: str
    quantite_g: float
    prix: Optional[float] = None
    promo: bool = False


class FenetreDayPlan(BaseModel):
    date: dt.date
    intensite: str
    items: list[PlanItem]
    totals: dict[str, float]


class FenetreScore(BaseModel):
    couverture_moyenne: float
    pct_micros_atteints: float
    cout_total: float
    ratio: float
    sous_couverts: list[str]


class WindowPlanResponse(BaseModel):
    anchor_date: dt.date
    length: int
    poids_used: float
    jours: list[FenetreDayPlan]
    shopping_list: list[ShoppingItem]
    score: FenetreScore
    warning: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/sante/schemas.py backend/tests/test_sante/test_fenetre_schemas.py
git commit -m "feat(sante): schemas API de la fenetre batch-cook"
```

---

### Task 8 : Service d'orchestration `generate_window` / `get_current_window`

**Files:**
- Create: `backend/app/services/sante/fenetre_service.py`
- Test: `backend/tests/test_sante/test_fenetre_service.py`

**Interfaces:**
- Consumes: `fenetre` (Task 2), `coverage` (Task 3), `optimize_ratio` (Task 4), `debt` (Task 5), `WindowPlan` (Task 6) ; helpers existants `calculate_daily_targets`, `load_aliments_dataframe`, `apply_superc_catalog_prices`, `calculate_plan_totals` ; helpers de `app.api.sante.plan` (`_resolve_intensity`, `_last_known_weight`) importés en **lazy** (éviter le cycle import).
- Produces:
  - `generate_window(session, day: dt.date|None=None, poids: float|None=None, force: bool=False) -> WindowPlan` — génère/écrase la fenêtre de l'ancre de `day`, persiste `WindowPlan` + une ligne `PlanNutrition` par jour (`quantites` = portion du jour ; `consumed` préservé si présent).
  - `get_current_window(session, day: dt.date|None=None) -> WindowPlan|None`.
  - `_prev_window_actuals(session, anchor) -> tuple[dict, dict]` — (Σ targets, Σ consumed) de la fenêtre précédente pour la dette.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_fenetre_service.py
import datetime as dt
import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.sante import MesureSante, NutritionGoal, PlanNutrition, WindowPlan


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(NutritionGoal(actif=True))
        s.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        s.commit()
        yield s


def _fake_df():
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres", "Fer",
            "Magnesium", "Omega 3", "VitA", "VitB1", "VitB2", "VitB3", "VitB5", "VitB6",
            "VitB9", "VitB12", "VitD", "VitE", "VitK", "Calcium", "Zinc", "Potassium",
            "Iode", "Selenium", "Phosphore"]
    data = {
        "Legume": [50, 3, 0.5, 8, 0.4] + [50] * (len(cols) - 5),
        "Riz":    [130, 3, 0.3, 28, 0.2] + [5] * (len(cols) - 5),
        "Poulet": [165, 31, 3.6, 0, 1.2] + [5] * (len(cols) - 5),
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


@pytest.fixture(autouse=True)
def _patch_engine_and_prices(monkeypatch, session):
    """Neutralise DB globale, scrape et catalogue réel : df factice + prix identité."""
    import app.core.db as db
    monkeypatch.setattr(db, "engine", session.get_bind())
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df: (df, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)


def test_generate_monday_window_persists_3_days(session):
    from app.services.sante.fenetre_service import generate_window
    wp = generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    assert wp.length == 3
    assert wp.food_set                       # non vide
    days = session.exec(select(PlanNutrition).where(
        PlanNutrition.date >= dt.date(2026, 7, 20))).all()
    assert {d.date for d in days} == {
        dt.date(2026, 7, 20), dt.date(2026, 7, 21), dt.date(2026, 7, 22)}
    # conservation : Σ portions/jour d'un aliment == food_set
    riz = next(iter(wp.food_set))
    total = sum((d.quantites or {}).get(riz, 0.0) for d in days)
    assert total == pytest.approx(wp.food_set[riz], rel=1e-6)


def test_debt_from_previous_window_consumption(session):
    """Une fenêtre précédente sous-consommée en VitD escalade sa priorité."""
    from app.services.sante.fenetre_service import generate_window
    # fenêtre précédente (jeu 2026-07-16 → 4 jours) avec conso VitD faible
    for i, d in enumerate([dt.date(2026, 7, 16), dt.date(2026, 7, 17),
                           dt.date(2026, 7, 18), dt.date(2026, 7, 19)]):
        session.add(PlanNutrition(
            date=d, targets={"VitD": 15.0}, consumed={"VitD": 1.0}))
    session.add(WindowPlan(anchor_date=dt.date(2026, 7, 16), length=4,
                           food_set={}, debt_series={"VitD": 1}))
    session.commit()
    wp = generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    assert wp.debt_series.get("VitD", 0) >= 2   # série incrémentée
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.sante.fenetre_service'`.

- [ ] **Step 3: Implement `fenetre_service.py`**

```python
# backend/app/services/sante/fenetre_service.py
"""Orchestration de la génération d'une fenêtre batch-cook (spec §1-§5).

Assemble : cibles/jour (base, sans J-1), somme fenêtre, dette (conso réelle de la
fenêtre précédente), prix Super C live, optimisation ratio, répartition/jour,
persistance WindowPlan + PlanNutrition/jour.
"""
from __future__ import annotations

import datetime as dt
import secrets
from typing import Optional

from sqlmodel import Session, select

from app.models.sante import PlanNutrition, WindowPlan
from app.services.sante import debt, fenetre
from app.services.sante.aliments import load_aliments_dataframe
from app.services.sante.adonis_pricing import apply_superc_catalog_prices
from app.services.sante.ratio_optimizer import optimize_ratio
from app.services.sante.targets import calculate_daily_targets
from app.services.sante.totals import calculate_plan_totals


def _refresh_prices_best_effort() -> None:
    """Rafraîchit les caches Super C (courant + circulaire) si périmés. Jamais
    bloquant (désactivé en test via STORE_PRICING_REFRESH=0)."""
    try:
        from app.services.cuisine import store_pricing
        store_pricing.refresh_all_if_stale()
    except Exception:
        pass


def _prev_window_actuals(session: Session, anchor: dt.date) -> tuple[dict, dict]:
    """(Σ targets, Σ consumed) de la fenêtre précédant `anchor`."""
    prev_anchor = fenetre.anchor_for(anchor - dt.timedelta(days=1))
    try:
        prev_days = fenetre.window_days(prev_anchor)
    except ValueError:
        return {}, {}
    t_sum: dict[str, float] = {}
    c_sum: dict[str, float] = {}
    rows = session.exec(select(PlanNutrition).where(PlanNutrition.date.in_(prev_days))).all()
    for r in rows:
        for k, v in (r.targets or {}).items():
            t_sum[k] = t_sum.get(k, 0.0) + float(v or 0.0)
        for k, v in (r.consumed or {}).items():
            c_sum[k] = c_sum.get(k, 0.0) + float(v or 0.0)
    return t_sum, c_sum


def generate_window(
    session: Session, day: Optional[dt.date] = None,
    poids: Optional[float] = None, force: bool = False,
) -> WindowPlan:
    from app.api.sante.plan import _last_known_weight, _resolve_intensity
    from app.services.sante import ensure_active_goal

    today = day or dt.date.today()
    anchor = fenetre.anchor_for(today)
    days = fenetre.window_days(anchor)
    goal = ensure_active_goal(session)
    if poids is None:
        poids = _last_known_weight(session, before=anchor)
    if poids is None:
        raise ValueError("Aucun poids connu et aucun poids fourni.")

    # 1) Cibles de base par jour (intensité résolue), sans compensation J-1.
    daily_targets: list[dict] = []
    intensities: list[str] = []
    for d in days:
        intensity, _ctx = _resolve_intensity(session, d, goal.sport_days)
        base, _comp = calculate_daily_targets(
            weight=poids, date=d, history=None, intensity=intensity,
            surplus_kcal_sport=goal.surplus_kcal_sport, rest_factor=goal.rest_factor,
            sport_days=goal.sport_days,
        )
        daily_targets.append(base)
        intensities.append(intensity)

    win_targets = fenetre.window_targets(daily_targets)

    # 2) Dette : report + escalade depuis la conso réelle de la fenêtre précédente.
    prev = session.exec(select(WindowPlan).where(WindowPlan.anchor_date < anchor)
                        .order_by(WindowPlan.anchor_date.desc())).first()
    prev_series = prev.debt_series if prev else None
    t_sum, c_sum = _prev_window_actuals(session, anchor)
    target_add, weight_mult, new_series = debt.carryover(t_sum, c_sum, prev_series)
    for k, extra in target_add.items():
        win_targets[k] = win_targets.get(k, 0.0) + extra

    # 3) Prix Super C live (best-effort) + catalogue re-tarifé.
    _refresh_prices_best_effort()
    df = load_aliments_dataframe(session)
    df, _priced = apply_superc_catalog_prices(df)

    # 4) Optimisation ratio couverture/coût sur la fenêtre.
    seed = secrets.randbelow(2**31) if force else None
    plan_items, warning, score = optimize_ratio(
        df, win_targets, budget_max_daily=win_targets.get("Prix_Max"),
        seed=seed, micro_weight_mult=weight_mult or None,
    )
    if plan_items is None:
        raise ValueError(warning or "Optimisation fenêtre impossible.")

    food_set = {it["Aliment"]: float(it["Quantite_g"]) for it in plan_items}

    # 5) Liste de courses (prix + promo best-effort).
    shopping = _build_shopping_list(food_set, df)

    # 6) Répartition par jour (prorata des calories-cibles) + persistance/jour.
    cal_targets = [float(t.get("Calories", 0.0)) for t in daily_targets]
    per_day = fenetre.split_by_day(food_set, cal_targets)
    for d, day_grams, day_tgt, intensity in zip(days, per_day, daily_targets, intensities):
        items = [{"Aliment": nom, "Quantite_g": g} for nom, g in day_grams.items()]
        totals = calculate_plan_totals(items, df)
        row = session.exec(select(PlanNutrition).where(PlanNutrition.date == d)).first()
        if row is None:
            row = PlanNutrition(date=d)
        row.poids_used = poids
        row.intensite = intensity
        row.base_targets = day_tgt
        row.targets = day_tgt
        row.quantites = day_grams
        row.totals = totals
        # `consumed` volontairement préservé (report conso réelle).
        session.add(row)

    # 7) Persistance WindowPlan.
    wp = session.exec(select(WindowPlan).where(WindowPlan.anchor_date == anchor)).first()
    if wp is None:
        wp = WindowPlan(anchor_date=anchor)
    wp.length = len(days)
    wp.poids_used = poids
    wp.food_set = food_set
    wp.shopping_list = shopping
    wp.score = score
    wp.debt_series = new_series
    wp.warning = warning or None
    session.add(wp)
    session.commit()
    session.refresh(wp)
    return wp


def _build_shopping_list(food_set: dict[str, float], df) -> list[dict]:
    """[{aliment, quantite_g, prix, promo}] — prix = Prix/100 g × grammes, promo
    best-effort via store_pricing (jamais bloquant)."""
    try:
        from app.services.cuisine import store_pricing
    except Exception:
        store_pricing = None
    out = []
    for nom, grams in food_set.items():
        prix = None
        if nom in df.index:
            try:
                prix = round(float(df.loc[nom, "Prix"]) * grams / 100.0, 2)
            except Exception:
                prix = None
        promo = False
        if store_pricing is not None:
            try:
                rec = store_pricing.recommend_store(nom)
                promo = bool(rec and rec.get("promo"))
            except Exception:
                promo = False
        out.append({"aliment": nom, "quantite_g": round(grams, 1), "prix": prix, "promo": promo})
    return out


def get_current_window(session: Session, day: Optional[dt.date] = None) -> WindowPlan | None:
    anchor = fenetre.anchor_for(day or dt.date.today())
    return session.exec(select(WindowPlan).where(WindowPlan.anchor_date == anchor)).first()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sante/fenetre_service.py backend/tests/test_sante/test_fenetre_service.py
git commit -m "feat(sante): service d'orchestration generate_window (cibles+dette+ratio+courses)"
```

---

### Task 9 : Routeur API `/sante/fenetre/*`

**Files:**
- Create: `backend/app/api/sante/fenetre.py`
- Modify: `backend/app/api/sante/__init__.py`
- Test: `backend/tests/test_sante/test_fenetre_api.py`

**Interfaces:**
- Consumes: `fenetre_service` (Task 8), schémas (Task 7).
- Produces: `POST /sante/fenetre/generate` (body `FenetreGenerateRequest`) et `GET /sante/fenetre/current?date=` → `WindowPlanResponse`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sante/test_fenetre_api.py
import datetime as dt
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.main import app
from app.core.db import get_session
from app.models.sante import MesureSante, NutritionGoal


def _fake_df():
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres", "Fer"]
    data = {"Legume": [50, 3, 0.5, 8, 0.4, 80, 6, 3],
            "Riz": [130, 3, 0.3, 28, 0.2, 0, 1, 0.5],
            "Poulet": [165, 31, 3.6, 0, 1.2, 0, 0, 1]}
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(NutritionGoal(actif=True))
        s.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        s.commit()
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df: (df, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)
    # Le routeur reconstruit les items/jour depuis son propre chargeur → le
    # patcher aussi pour que la réponse reflète le df factice.
    import app.api.sante.fenetre as fenetre_api
    monkeypatch.setattr(fenetre_api, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fenetre_api, "apply_superc_catalog_prices", lambda df: (df, []))
    app.dependency_overrides[get_session] = lambda: Session(engine)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_generate_then_get_current(client):
    r = client.post("/sante/fenetre/generate", json={"date": "2026-07-20", "poids": 51.0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["length"] == 3
    assert len(body["jours"]) == 3
    assert any(j["items"] for j in body["jours"])   # portions/jour reconstruites
    assert body["shopping_list"]
    assert "ratio" in body["score"]

    r2 = client.get("/sante/fenetre/current", params={"date": "2026-07-21"})
    assert r2.status_code == 200
    assert r2.json()["anchor_date"] == "2026-07-20"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre_api.py -v`
Expected: FAIL — 404 sur `/sante/fenetre/generate` (route absente).

- [ ] **Step 3: Implement the router and mount it**

```python
# backend/app/api/sante/fenetre.py
"""Endpoints de la fenêtre batch-cook (spec §5)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.sante.schemas import (
    FenetreDayPlan, FenetreGenerateRequest, FenetreScore, PlanItem,
    ShoppingItem, WindowPlanResponse,
)
from app.core.db import get_session
from app.models.sante import PlanNutrition, WindowPlan
from app.services.sante import fenetre, fenetre_service
from app.services.sante.adonis_pricing import apply_superc_catalog_prices
from app.services.sante.aliments import load_aliments_dataframe

router = APIRouter()


def _day_plans(session: Session, wp: WindowPlan, df) -> list[FenetreDayPlan]:
    days = fenetre.window_days(wp.anchor_date)
    out: list[FenetreDayPlan] = []
    rows = {r.date: r for r in session.exec(
        select(PlanNutrition).where(PlanNutrition.date.in_(days))).all()}
    for d in days:
        r = rows.get(d)
        items: list[PlanItem] = []
        for nom, g in ((r.quantites if r else None) or {}).items():
            if nom not in df.index:
                continue
            row = df.loc[nom]
            u = float(g) / 100.0
            items.append(PlanItem(
                aliment=nom, quantite_g=float(g), quantite_str=f"{float(g):.0f}g",
                calories=float(row["Energie"]) * u, proteines=float(row["Proteines"]) * u,
                lipides=float(row["Lipides"]) * u, glucides=float(row["Glucides"]) * u,
                prix=float(row["Prix"]) * u))
        out.append(FenetreDayPlan(
            date=d, intensite=(r.intensite if r else "none") or "none",
            items=items, totals=(r.totals if r else {}) or {}))
    return out


def _to_response(session: Session, wp: WindowPlan) -> WindowPlanResponse:
    df = load_aliments_dataframe(session)
    df, _ = apply_superc_catalog_prices(df)
    s = wp.score or {}
    return WindowPlanResponse(
        anchor_date=wp.anchor_date, length=wp.length, poids_used=float(wp.poids_used or 0.0),
        jours=_day_plans(session, wp, df),
        shopping_list=[ShoppingItem(**it) for it in (wp.shopping_list or [])],
        score=FenetreScore(
            couverture_moyenne=float(s.get("couverture_moyenne", 0.0)),
            pct_micros_atteints=float(s.get("pct_micros_atteints", 0.0)),
            cout_total=float(s.get("cout_total", 0.0)), ratio=float(s.get("ratio", 0.0)),
            sous_couverts=list(s.get("sous_couverts", []))),
        warning=wp.warning)


@router.post("/fenetre/generate", response_model=WindowPlanResponse)
def generate_fenetre(payload: FenetreGenerateRequest, session: Session = Depends(get_session)):
    try:
        wp = fenetre_service.generate_window(
            session, day=payload.date, poids=payload.poids, force=payload.force)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return _to_response(session, wp)


@router.get("/fenetre/current", response_model=WindowPlanResponse)
def current_fenetre(date: Optional[dt.date] = Query(None), session: Session = Depends(get_session)):
    wp = fenetre_service.get_current_window(session, day=date)
    if wp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune fenêtre pour cette date.")
    return _to_response(session, wp)
```

Dans `backend/app/api/sante/__init__.py` :
```python
from . import fenetre, mesures, nutrition, plan, score, wellbeing
...
router.include_router(fenetre.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sante/test_fenetre_api.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/sante/fenetre.py backend/app/api/sante/__init__.py backend/tests/test_sante/test_fenetre_api.py
git commit -m "feat(sante): endpoints /sante/fenetre/generate + /current"
```

---

### Task 10 : Scheduler — génère la fenêtre les lun/jeu

**Files:**
- Modify: `backend/app/services/scheduler/jobs/nutrition_plan.py`
- Modify: `backend/app/services/scheduler/scheduler.py`
- Test: `backend/tests/test_scheduler/test_nutrition_plan_job.py`

**Interfaces:**
- Produces: `nutrition_plan.run(session)` génère la **fenêtre** de l'ancre quand `today.weekday() in (0, 3)` (best-effort : jamais fatal), sinon conserve le comportement plan-du-jour. Nouveau cron `nutrition_fenetre` lun+jeu 06:30.

- [ ] **Step 1: Write the failing test**

```python
# ajouter à backend/tests/test_scheduler/test_nutrition_plan_job.py
import datetime as dt
import pandas as pd
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.sante import MesureSante, NutritionGoal, WindowPlan


def _fake_df():
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres", "Fer"]
    data = {"Legume": [50, 3, 0.5, 8, 0.4, 80, 6, 3], "Riz": [130, 3, 0.3, 28, 0.2, 0, 1, 0.5],
            "Poulet": [165, 31, 3.6, 0, 1.2, 0, 0, 1]}
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


def test_generates_window_on_monday(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(NutritionGoal(actif=True))
        s.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        s.commit()
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df: (df, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)
    from app.services.scheduler.jobs import nutrition_plan
    monkeypatch.setattr(nutrition_plan.dt, "date", type("D", (dt.date,), {
        "today": staticmethod(lambda: dt.date(2026, 7, 20))}))
    with Session(engine) as s:
        nutrition_plan.run(s)
        assert s.exec(select(WindowPlan).where(
            WindowPlan.anchor_date == dt.date(2026, 7, 20))).first() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scheduler/test_nutrition_plan_job.py::test_generates_window_on_monday -v`
Expected: FAIL — aucune `WindowPlan` créée (le job ne gère pas encore la fenêtre).

- [ ] **Step 3: Extend the job**

Dans `backend/app/services/scheduler/jobs/nutrition_plan.py`, en tête de `run`, après le calcul de `today` :
```python
    # Jours de batch-cooking (lun/jeu) : génère la fenêtre (best-effort).
    if today.weekday() in (0, 3):
        try:
            from app.services.sante.fenetre_service import generate_window
            wp = generate_window(session, day=today)
            return f"Fenêtre nutrition générée pour {today} ({wp.length} j, {len(wp.food_set)} aliments)"
        except Exception as exc:  # jamais fatal
            return f"Fenêtre nutrition non générée pour {today} : {exc}"
```
(Le reste de la fonction — plan du jour — reste inchangé pour les autres jours.)

Dans `backend/app/services/scheduler/scheduler.py`, ajouter un cron dédié lun+jeu 06:30 (le job quotidien existant reste pour les autres jours) :
```python
    scheduler.add_job(run_job, "cron", day_of_week="mon,thu", hour=6, minute=30,
                      args=["nutrition_fenetre", nutrition_plan.run],
                      id="nutrition_fenetre", replace_existing=True, misfire_grace_time=3600)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_scheduler/test_nutrition_plan_job.py -v`
Expected: PASS (nouveau test + tests existants du job).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scheduler/jobs/nutrition_plan.py backend/app/services/scheduler/scheduler.py backend/tests/test_scheduler/test_nutrition_plan_job.py
git commit -m "feat(scheduler): genere la fenetre nutrition les lun/jeu a 06:30"
```

---

## Phase 3 — Frontend (onglet « Fenêtre »)

### Task 11 : Client API + hooks React Query de la fenêtre

**Files:**
- Modify: `frontend/lib/sante.ts` (client fetch)
- Modify: `frontend/lib/queries/sante.ts` (hooks)
- Test: `frontend/__tests__/sante/fenetre-queries.test.ts`

**Interfaces:**
- Produces: types `WindowPlanResponse`, `FenetreDayPlan`, `ShoppingItem`, `FenetreScore` ; méthodes `santeApi.fenetreCurrent(date?)`, `santeApi.generateFenetre(body)` (via le helper `api()` de `@/lib/api`) ; clé `santeKeys.fenetre(date?)` ; hooks `useFenetreCurrent(date?)`, `useGenerateFenetre()`.

- [ ] **Step 1: Inspect existing patterns**

Lire `frontend/lib/sante.ts` (objet `santeApi`, helper `api` de `./api`) et `frontend/lib/queries/sante.ts` (fabrique `santeKeys`, hooks `usePlanToday`/mutations) pour ajouter les nouvelles entrées **dans l'objet `santeApi` existant** et suivre les conventions de clés/invalidation.

- [ ] **Step 2: Write the failing test**

```ts
// frontend/__tests__/sante/fenetre-queries.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du helper HTTP `api` (hoisted → référence sûre dans la factory vi.mock).
const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: apiMock }));

import { santeApi } from "@/lib/sante";

beforeEach(() => {
  apiMock.mockReset();
  apiMock.mockResolvedValue({ anchor_date: "2026-07-20", length: 3, jours: [], shopping_list: [], score: {} });
});

describe("fenetre client", () => {
  it("POST generate hits the right endpoint", async () => {
    await santeApi.generateFenetre({ date: "2026-07-20", poids: 51 });
    expect(apiMock.mock.calls[0][0]).toBe("/sante/fenetre/generate");
    expect(apiMock.mock.calls[0][1].method).toBe("POST");
  });
  it("GET current passes the date param", async () => {
    await santeApi.fenetreCurrent("2026-07-21");
    expect(apiMock.mock.calls[0][0]).toContain("/sante/fenetre/current");
    expect(apiMock.mock.calls[0][0]).toContain("date=2026-07-21");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/sante/fenetre-queries.test.ts`
Expected: FAIL — `santeApi.generateFenetre is not a function`.

- [ ] **Step 4: Add types + client methods + hooks**

Dans `frontend/lib/sante.ts` — ajouter les types (près des autres `export type`) :
```ts
export type ShoppingItem = { aliment: string; quantite_g: number; prix: number | null; promo: boolean };
export type FenetrePlanItem = { aliment: string; quantite_g: number; quantite_str: string; calories: number; proteines: number; lipides: number; glucides: number; prix: number };
export type FenetreDayPlan = { date: string; intensite: string; items: FenetrePlanItem[]; totals: Record<string, number> };
export type FenetreScore = { couverture_moyenne: number; pct_micros_atteints: number; cout_total: number; ratio: number; sous_couverts: string[] };
export type WindowPlanResponse = { anchor_date: string; length: number; poids_used: number; jours: FenetreDayPlan[]; shopping_list: ShoppingItem[]; score: FenetreScore; warning: string | null };
```
… puis, **dans l'objet `santeApi` existant** (le fichier fait déjà `import { api } from "./api"`), ajouter ces deux méthodes :
```ts
  fenetreCurrent: (date?: string) =>
    api<WindowPlanResponse>(`/sante/fenetre/current${date ? `?date=${encodeURIComponent(date)}` : ""}`),
  generateFenetre: (body: { date?: string; poids?: number; force?: boolean }) =>
    api<WindowPlanResponse>("/sante/fenetre/generate", { method: "POST", body: JSON.stringify(body) }),
```
(Le helper `api()` met déjà `Content-Type: application/json` et lève sur les réponses non-OK.)

Dans `frontend/lib/queries/sante.ts` — ajouter la clé dans la fabrique `santeKeys` :
```ts
  fenetre: (date?: string) => [...santeKeys.all, "fenetre", date ?? "current"] as const,
```
… et les hooks :
```ts
export function useFenetreCurrent(date?: string) {
  return useQuery({
    queryKey: santeKeys.fenetre(date),
    queryFn: () => santeApi.fenetreCurrent(date),
    retry: false,
  });
}

export function useGenerateFenetre() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { date?: string; poids?: number; force?: boolean }) => santeApi.generateFenetre(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...santeKeys.all, "fenetre"] }),
  });
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run __tests__/sante/fenetre-queries.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/sante.ts frontend/lib/queries/sante.ts frontend/__tests__/sante/fenetre-queries.test.ts
git commit -m "feat(sante-ui): client + hooks React Query de la fenetre"
```

---

### Task 12 : Onglet « Fenêtre » (plan/jour + liste à cocher + score)

**Files:**
- Create: `frontend/components/sante/FenetreTab.tsx`
- Modify: `frontend/components/sante/Sante.tsx`
- Test: `frontend/__tests__/sante/fenetre-tab.test.tsx`

**Interfaces:**
- Consumes: `useFenetreCurrent`, `useGenerateFenetre` (Task 11).
- Produces: composant `FenetreTab` (poids + « Générer » / « Régénérer », plan par jour, liste de courses cochable avec prix + badge promo, bloc score + micros sous-couverts) ; nouvel onglet `fenetre` dans `Sante.tsx`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/__tests__/sante/fenetre-tab.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FenetreTab } from "@/components/sante/FenetreTab";

vi.mock("@/lib/queries/sante", () => ({
  useFenetreCurrent: () => ({
    data: {
      anchor_date: "2026-07-20", length: 3, poids_used: 51,
      jours: [{ date: "2026-07-20", intensite: "medium", items: [], totals: {} }],
      shopping_list: [{ aliment: "Riz", quantite_g: 900, prix: 1.8, promo: true }],
      score: { couverture_moyenne: 0.82, pct_micros_atteints: 70, cout_total: 42, ratio: 0.0195, sous_couverts: ["VitD"] },
      warning: null,
    }, isLoading: false, isError: false,
  }),
  useGenerateFenetre: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function wrap(ui: React.ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>;
}

describe("FenetreTab", () => {
  it("shows the shopping list and score", () => {
    render(wrap(<FenetreTab goal={null} onSaveMesure={vi.fn()} />));
    expect(screen.getByText("Riz")).toBeInTheDocument();
    expect(screen.getByText(/70/)).toBeInTheDocument();       // % micros
    expect(screen.getByText("VitD")).toBeInTheDocument();     // sous-couvert
    expect(screen.getByText(/promo/i)).toBeInTheDocument();   // badge
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/sante/fenetre-tab.test.tsx`
Expected: FAIL — `FenetreTab` introuvable.

- [ ] **Step 3: Implement `FenetreTab.tsx`**

```tsx
// frontend/components/sante/FenetreTab.tsx
"use client";

import { useState } from "react";
import { useFenetreCurrent, useGenerateFenetre } from "@/lib/queries/sante";

export function FenetreTab({
  goal, onSaveMesure,
}: { goal: any; onSaveMesure: (m: { date: string; poids?: number }) => Promise<void> }) {
  const fenetreQ = useFenetreCurrent();
  const generate = useGenerateFenetre();
  const [poids, setPoids] = useState<string>("");
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  const win = fenetreQ.data ?? null;

  const onGenerate = async (force = false) => {
    const p = poids ? parseFloat(poids) : undefined;
    if (p) await onSaveMesure({ date: new Date().toISOString().slice(0, 10), poids: p });
    await generate.mutateAsync({ poids: p, force });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Poids (kg)
          <input value={poids} onChange={(e) => setPoids(e.target.value)} inputMode="decimal"
            className="ml-2 w-24 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] px-2 py-1" />
        </label>
        <button onClick={() => onGenerate(false)} disabled={generate.isPending}
          className="rounded-[var(--radius)] bg-[var(--primary)] px-3 py-1.5 text-sm text-[var(--primary-foreground)]">
          {generate.isPending ? "…" : "Générer la fenêtre"}
        </button>
        {win && (
          <button onClick={() => onGenerate(true)} disabled={generate.isPending}
            className="rounded-[var(--radius)] bg-[var(--muted)] px-3 py-1.5 text-sm">Régénérer</button>
        )}
      </div>

      {!win ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune fenêtre. Entre ton poids puis « Générer ».</p>
      ) : (
        <>
          <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
            <h3 className="mb-2 font-medium">Score</h3>
            <div className="flex flex-wrap gap-6 text-sm">
              <div><b>{win.score.pct_micros_atteints.toFixed(0)}%</b> micros atteints</div>
              <div>Couverture <b>{(win.score.couverture_moyenne * 100).toFixed(0)}%</b></div>
              <div>Coût <b>{win.score.cout_total.toFixed(2)} $</b></div>
              <div>Ratio <b>{(win.score.ratio * 1000).toFixed(1)}</b>/1000$</div>
            </div>
            {win.score.sous_couverts.length > 0 && (
              <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                Sous-couverts : {win.score.sous_couverts.map((k) => (
                  <span key={k} className="mr-1 rounded bg-[var(--muted)] px-1.5 py-0.5">{k}</span>
                ))}
              </p>
            )}
          </section>

          <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
            <h3 className="mb-2 font-medium">Liste de courses ({win.length} j)</h3>
            <ul className="divide-y divide-[var(--border)]">
              {win.shopping_list.map((it) => (
                <li key={it.aliment} className="flex items-center gap-3 py-1.5 text-sm">
                  <input type="checkbox" checked={!!checked[it.aliment]}
                    onChange={(e) => setChecked((c) => ({ ...c, [it.aliment]: e.target.checked }))} />
                  <span className={checked[it.aliment] ? "line-through opacity-50" : ""}>{it.aliment}</span>
                  <span className="text-[var(--muted-foreground)]">{it.quantite_g.toFixed(0)} g</span>
                  {it.promo && <span className="rounded bg-[var(--primary)] px-1.5 py-0.5 text-xs text-[var(--primary-foreground)]">promo</span>}
                  <span className="ml-auto tabular-nums">{it.prix != null ? `${it.prix.toFixed(2)} $` : "—"}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
            <h3 className="mb-2 font-medium">Par jour</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {win.jours.map((j) => (
                <div key={j.date} className="rounded-[var(--radius)] bg-[var(--muted)] p-2 text-xs">
                  <div className="font-medium">{j.date} · {j.intensite}</div>
                  <ul>{j.items.map((it) => (
                    <li key={it.aliment} className="flex justify-between">
                      <span>{it.aliment}</span><span>{it.quantite_g.toFixed(0)} g</span>
                    </li>))}</ul>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire the tab into `Sante.tsx`**

Dans `frontend/components/sante/Sante.tsx` :
1. Ajouter `ShoppingCart` à l'import `lucide-react` **existant** (`import { Sun, TrendingUp, Activity, Target, Camera, ShoppingCart } from "lucide-react";`) et importer le composant : `import { FenetreTab } from "./FenetreTab";`
2. Étendre le type et la liste d'onglets :
```tsx
type Tab = "jour" | "fenetre" | "tendance" | "composition" | "objectif" | "progression";
// dans TABS, après "jour" :
{ id: "fenetre", label: "Fenêtre", Icon: ShoppingCart },
```
3. Rendre l'onglet (dans le bloc de contenu) :
```tsx
{tab === "fenetre" && <FenetreTab goal={goal} onSaveMesure={onSaveMesure} />}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run __tests__/sante/fenetre-tab.test.tsx`
Expected: PASS.

Run: `cd frontend && npx tsc --noEmit`
Expected: pas d'erreur de type.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/sante/FenetreTab.tsx frontend/components/sante/Sante.tsx frontend/__tests__/sante/fenetre-tab.test.tsx
git commit -m "feat(sante-ui): onglet Fenetre (plan/jour + liste a cocher + score)"
```

---

## Validation finale

- [ ] **Backend complet** : `cd backend && python -m pytest tests/test_sante tests/test_scheduler tests/test_migrations.py -q` → tout PASS.
- [ ] **Frontend** : `cd frontend && npx vitest run __tests__/sante && npx tsc --noEmit` → PASS.
- [ ] **Fumée manuelle** (optionnel) : lancer le backend, `POST /sante/fenetre/generate` avec `{"date":"<un lundi>","poids":51}`, vérifier la réponse (3 jours, liste de courses, score) puis `GET /sante/fenetre/current`.

## Notes de séquencement pour l'exécuteur

- Ordre strict Phase 1 → 2 → 3 (dépendances de types). À l'intérieur d'une phase, l'ordre des tâches est celui du document.
- Sous-projet **B** (panier Instacart auto) : **hors de ce plan**, spec + plan dédiés plus tard.
- Écart assumé vs design : le ratio est réalisé par **balayage du poids-prix** (chemin simple sanctionné §2), pas par Dinkelbach — plus robuste et testable, même comportement visé (meilleure couverture/$, promos exploitées, micros chers lâchés sous budget serré, forcés par la dette).
