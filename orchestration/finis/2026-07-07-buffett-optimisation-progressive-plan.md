# Progression live de l'optimisation de portefeuille Buffett — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pendant la phase d'optimisation DE du run Buffett automatique (peut durer des heures), afficher une barre de progression (génération/convergence) et le meilleur portefeuille trouvé jusqu'ici, mis à jour en direct — au lieu de rien afficher et de montrer une allocation périmée du run précédent.

**Architecture:** `optimize_portfolio_de` (backend) gagne un callback `on_new_best(W)` déclenché à chaque nouveau record global (toutes les 10 seeds DE confondues), throttlé à 2s. `runner.py` câble ce callback pour discrétiser et persister l'allocation en DB (`update_allocations`, déjà existant) et câble aussi le module `optimization_progress` (déjà existant, déjà utilisé par le bouton manuel) pour la barre génération/convergence. Aucun nouvel endpoint : les endpoints existants (`/finance/buffett/runs/{id}`, `/finance/portfolio/progress`) exposent déjà ces données une fois persistées. Le frontend étend le polling déjà en place pour afficher la barre et rafraîchir la vue détail du run pendant qu'il tourne.

**Tech Stack:** Python (FastAPI, SQLModel, scipy.optimize, numpy), pytest, Next.js/React (TypeScript).

## Global Constraints

- `on_new_best` (et toute nouvelle logique de progression) ne doit **jamais** interrompre l'optimisation ou le run en cas d'erreur — toujours encapsulé dans un `try/except` qui ne fait qu'un `print`, comme le fait déjà `_report`/`progress_cb` existant.
- Le comportement et la valeur de retour finale de `optimize_portfolio_de` (`W`, `starr`) restent **strictement identiques** à aujourd'hui — c'est une extraction/refactor + ajout d'un callback optionnel, pas un changement de logique d'optimisation.
- Pas de nouvel endpoint backend : réutiliser `/finance/buffett/runs/{run_id}` et `/finance/portfolio/progress` existants.
- Spec source : `orchestration/a-faire/2026-07-07-buffett-optimisation-progressive-design.md`.

---

### Task 1 : `optimize_portfolio_de` — callback `on_new_best` + extraction de la conversion en allocation

**Files:**
- Modify: `backend/app/services/finance/buffett/optimizer.py`
- Test: `backend/tests/test_finance/test_optimizer_robust.py`

**Interfaces:**
- Produces: `optimize_portfolio_de(..., on_new_best: Callable[[np.ndarray], None] | None = None) -> tuple[np.ndarray, float]` — signature étendue, comportement de retour inchangé. `on_new_best` reçoit `W` (même format que la valeur de retour : `np.ndarray [n_tickers x n_brokers]`, fraction du capital total), appelé au minimum une fois à la toute fin (résultat final), et pendant l'optimisation à chaque nouveau record global toutes seeds confondues (throttlé 2s).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_finance/test_optimizer_robust.py (ajouter à la fin du fichier)

def test_de_calls_on_new_best_with_decreasing_energy(monkeypatch):
    """on_new_best doit être appelé au moins une fois (résultat final garanti),
    et la matrice W qu'il reçoit à chaque appel doit correspondre à une
    allocation faisable (même contrat que la valeur de retour finale)."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_N_SEEDS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(1)
    n = 20
    R = rng.normal(0.0006, 0.02, (700, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    calls: list[np.ndarray] = []
    W_final, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        on_new_best=lambda W: calls.append(W.copy()),
    )

    assert len(calls) >= 1
    for W in calls:
        assert np.isfinite(W).all()
        assert abs(W.sum() - 1.0) < 1e-6   # capital total investi = 100%, même contrat que le retour final
    # Le dernier appel (post-polish) doit correspondre exactement au résultat final retourné.
    assert np.allclose(calls[-1], W_final)


def test_de_without_on_new_best_is_unaffected(monkeypatch):
    """on_new_best=None (défaut) : comportement 100% identique à avant -- même
    résultat que test_de_returns_feasible_finite_weights, juste sans callback."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_N_SEEDS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(2)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
    )
    assert np.isfinite(W).all()
    assert abs(W.sum() - 1.0) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_finance/test_optimizer_robust.py::test_de_calls_on_new_best_with_decreasing_energy -v`
Expected: FAIL with `TypeError: optimize_portfolio_de() got an unexpected keyword argument 'on_new_best'`

- [ ] **Step 3: Add `import time`**

`backend/app/services/finance/buffett/optimizer.py` lines 1-9, ajouter l'import :

```python
"""Optimiseur de portefeuille STARR via Monte Carlo + copule de Vine."""

from __future__ import annotations

import time

import numpy as np
from scipy import stats
from scipy.optimize import LinearConstraint, minimize

from .config import Config
```

- [ ] **Step 4: Étendre la signature de `optimize_portfolio_de`**

Dans `backend/app/services/finance/buffett/optimizer.py`, la signature actuelle (ligne ~339) :

```python
def optimize_portfolio_de(
    tickers: list[str],
    returns,          # pd.DataFrame de rendements journaliers
    matrix_access: list,
    active_brokers: list[str],
    seed: int = 42,
    progress_cb=None,   # callable(iteration:int, convergence:float) | None
    n_sim: int | None = None,
    alpha: float | None = None,
    downside_weight: float | None = None,
    min_position: float | None = None,
) -> tuple[np.ndarray, float]:
```

devient :

```python
def optimize_portfolio_de(
    tickers: list[str],
    returns,          # pd.DataFrame de rendements journaliers
    matrix_access: list,
    active_brokers: list[str],
    seed: int = 42,
    progress_cb=None,   # callable(iteration:int, convergence:float) | None
    on_new_best=None,   # callable(W: np.ndarray[n_tickers x n_brokers]) | None
    n_sim: int | None = None,
    alpha: float | None = None,
    downside_weight: float | None = None,
    min_position: float | None = None,
) -> tuple[np.ndarray, float]:
```

- [ ] **Step 5: Extraire `_to_broker_matrix` + throttle, avant la boucle multi-seed**

Dans le même fichier, le bloc actuel (autour de la ligne 465-476) :

```python
    min_gen = int(Config.STARR_DE_MIN_GENERATIONS)
    max_gen = int(Config.STARR_DE_MAX_GENERATIONS)   # garde-fou, pas l'arrêt normal
    n_seeds = max(1, int(Config.STARR_DE_N_SEEDS))
    de_tol = float(Config.STARR_DE_TOL)

    # ── Multi-seed : chaque run s'arrête sur convergence naturelle de la
    # population (pas sur un plafond de générations), avec un minimum de
    # générations pour éviter un arrêt prématuré. On garde le meilleur des N
    # seeds et on logge l'écart entre elles (mesure de robustesse : si les
    # scores divergent fort d'une seed à l'autre, le paysage a plusieurs
    # optima locaux comparables et il ne faut pas se fier à un seul run).
    runs = []   # (energie, x, nit, convergence_naturelle)
    for k in range(n_seeds):
```

devient :

```python
    min_gen = int(Config.STARR_DE_MIN_GENERATIONS)
    max_gen = int(Config.STARR_DE_MAX_GENERATIONS)   # garde-fou, pas l'arrêt normal
    n_seeds = max(1, int(Config.STARR_DE_N_SEEDS))
    de_tol = float(Config.STARR_DE_TOL)

    # ── Conversion vecteur DE brut -> allocation par broker, réutilisée pour le
    # résultat final ET les mises à jour progressives (on_new_best). Applique la
    # contrainte DURE (projette sur le portefeuille faisable le plus proche qui
    # respecte exactement défensif/pays/plafond par action -- remplace le plafond
    # + la pénalité douce, qui ne servaient qu'à guider la recherche DE).
    is_etf_inv = is_etf_full[inv_idx]

    def _to_broker_matrix(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raw = np.maximum(x, 0.0)
        s = raw.sum()
        w_inv = raw / s if s > 0 else raw
        w_inv = project_lookthrough_hard(
            w_inv, d_vec, C_mat, min_def, max_country, is_etf_inv, max_position,
        )
        w = np.zeros(num_t)
        for k2, i2 in enumerate(inv_idx):
            w[i2] = w_inv[k2]
        W = split_budget_to_brokers(w, access, b_ratios, min_position)
        return w_inv, W

    _last_emit_t = 0.0

    def _maybe_emit_progress(x: np.ndarray) -> None:
        nonlocal _last_emit_t
        if on_new_best is None:
            return
        now = time.time()
        if now - _last_emit_t < 2.0:   # throttle : évite le spam DB en tout début de DE
            return
        _last_emit_t = now
        try:
            _, w_matrix = _to_broker_matrix(x)
            on_new_best(w_matrix)
        except Exception:
            pass  # la progression ne doit jamais casser l'optimisation

    global_best_energy = float("inf")   # partagé entre les 10 seeds (pas remis à zéro à chaque seed)

    # ── Multi-seed : chaque run s'arrête sur convergence naturelle de la
    # population (pas sur un plafond de générations), avec un minimum de
    # générations pour éviter un arrêt prématuré. On garde le meilleur des N
    # seeds et on logge l'écart entre elles (mesure de robustesse : si les
    # scores divergent fort d'une seed à l'autre, le paysage a plusieurs
    # optima locaux comparables et il ne faut pas se fier à un seul run).
    runs = []   # (energie, x, nit, convergence_naturelle)
    for k in range(n_seeds):
```

- [ ] **Step 6: Émettre la progression à chaque nouveau record global, dans la boucle de générations**

Le bloc actuel (autour de la ligne 491-501) :

```python
        nit = 0
        converged_naturally = False
        for _ in solver:
            nit += 1
            _report(solver.convergence)
            if nit >= min_gen and solver.converged():
                converged_naturally = True
                break
            if nit >= max_gen:
                break
        runs.append((float(solver.population_energies[0]), solver.x.copy(), nit, converged_naturally))
```

devient :

```python
        nit = 0
        converged_naturally = False
        for _ in solver:
            nit += 1
            _report(solver.convergence)
            if solver.population_energies[0] < global_best_energy:
                global_best_energy = float(solver.population_energies[0])
                _maybe_emit_progress(solver.x)
            if nit >= min_gen and solver.converged():
                converged_naturally = True
                break
            if nit >= max_gen:
                break
        runs.append((float(solver.population_energies[0]), solver.x.copy(), nit, converged_naturally))
```

- [ ] **Step 7: Remplacer la conversion finale dupliquée par `_to_broker_matrix` + émission finale garantie**

Le bloc actuel (fin de la fonction, autour de la ligne 529-557) :

```python
    raw = np.maximum(best_x, 0.0)
    s = raw.sum()
    w_inv = raw / s if s > 0 else raw

    # Contrainte DURE : projette sur le portefeuille faisable le plus proche qui
    # respecte exactement défensif/pays/plafond par action (remplace le plafond
    # + la pénalité douce, qui ne servaient qu'à guider la recherche DE).
    is_etf_inv = is_etf_full[inv_idx]
    w_inv = project_lookthrough_hard(
        w_inv, d_vec, C_mat, min_def, max_country, is_etf_inv, max_position,
    )

    # STARR PUR (sans le malus de cardinalité, qui ne sert qu'à orienter l'optimiseur)
    # — mesuré sur le portefeuille final déjà projeté (contraintes garanties).
    starr = -neg_starr(w_inv, sim_rets, mean_daily, alpha, downside_weight)
    if not np.isfinite(starr):
        starr = 0.0
    print(f"    * STARR final : {starr:.3f}")

    # Remappage vers la liste complète des tickers (non-investissables = 0).
    w = np.zeros(num_t)
    for k, i in enumerate(inv_idx):
        w[i] = w_inv[k]

    # Répartition par broker (cf. split_budget_to_brokers) : déploiement du budget
    # parmi les titres disponibles ; les positions < min_position restent en cash
    # (on ne force pas le 100 %).
    W = split_budget_to_brokers(w, access, b_ratios, min_position)
    return W, starr
```

devient :

```python
    w_inv, W = _to_broker_matrix(best_x)

    # STARR PUR (sans le malus de cardinalité, qui ne sert qu'à orienter l'optimiseur)
    # — mesuré sur le portefeuille final déjà projeté (contraintes garanties).
    starr = -neg_starr(w_inv, sim_rets, mean_daily, alpha, downside_weight)
    if not np.isfinite(starr):
        starr = 0.0
    print(f"    * STARR final : {starr:.3f}")

    if on_new_best is not None:
        try:
            on_new_best(W)
        except Exception:
            pass  # la progression ne doit jamais casser le retour du résultat final

    return W, starr
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_finance/test_optimizer_robust.py -v`
Expected: PASS (les 4 tests du fichier, dont les 2 nouveaux et les 2 pré-existants inchangés)

- [ ] **Step 9: Commit**

```bash
cd backend
git add app/services/finance/buffett/optimizer.py tests/test_finance/test_optimizer_robust.py
git commit -m "$(cat <<'EOF'
feat(buffett): callback on_new_best pour l'optimisation DE

Extrait la conversion vecteur DE -> allocation par broker dans
_to_broker_matrix (reutilisee pour le resultat final et les mises a
jour progressives), et ajoute un callback optionnel declenche a
chaque nouveau meilleur portefeuille (toutes seeds confondues,
throttle 2s). Comportement de retour inchange (on_new_best=None par
defaut).
EOF
)"
```

---

### Task 2 : `runner.py` — câbler la barre de progression + la persistance progressive sur le run automatique

**Files:**
- Modify: `backend/app/services/finance/buffett/runner.py`
- Test: `backend/tests/test_finance/test_buffett_progressive_allocation.py` (nouveau)

**Interfaces:**
- Consumes: `optimize_portfolio_de(..., progress_cb=..., on_new_best=...)` de la Task 1 ; `optimization_progress.start/set_phase/update_de/finish` (module existant, déjà utilisé par `backend/app/api/finance/buffett.py`) ; `reporting.update_allocations(session, run_id, alloc, reset=True)` (existant, signature inchangée).
- Produces: aucune nouvelle interface publique — glue interne à `run_buffett_analysis`.

- [ ] **Step 1: Write the failing test — `update_allocations` remplace, n'accumule pas**

Ce test valide la propriété exacte dont dépend l'affichage progressif : un deuxième
appel à `update_allocations` pour le même run doit effacer l'allocation laissée par
le premier, pas l'empiler. C'est aussi ce qui règle le bug découvert dans la spec
(`BuffettRunResult.ticker` est `unique=True` — une seule ligne par ticker, toutes
runs confondues — donc sans ce comportement, un run en cours peut afficher des
tickers alloués par le run précédent).

```python
# backend/tests/test_finance/test_buffett_progressive_allocation.py
"""update_allocations(reset=True, par defaut) doit remplacer entierement
l'allocation d'un run a chaque appel -- c'est ce qui permet d'afficher le
meilleur portefeuille trouve jusqu'ici pendant l'optimisation DE (qui peut
durer des heures) sans laisser de residu de l'appel precedent."""

from sqlmodel import select

from app.models.finance import BuffettRunResult
from app.services.finance.buffett.reporting import update_allocations


def test_update_allocations_replaces_previous_progressive_snapshot(mem_session):
    for t in ["AAPL", "MSFT", "GOOG"]:
        mem_session.add(BuffettRunResult(run_id=1, ticker=t, chance_moat=90.0))
    mem_session.commit()

    # Premiere estimation "meilleur jusqu'ici" : AAPL + MSFT
    update_allocations(mem_session, 1, [
        {"Ticker": "AAPL", "Broker": "IBKR", "Poids total (%)": 60.0},
        {"Ticker": "MSFT", "Broker": "IBKR", "Poids total (%)": 40.0},
    ])
    rows = {r.ticker: r.allocation_pct for r in mem_session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == 1)
    ).all()}
    assert rows["AAPL"] == 60.0
    assert rows["MSFT"] == 40.0
    assert rows["GOOG"] is None

    # Le DE trouve un meilleur portefeuille (GOOG remplace MSFT) : le nouvel appel
    # doit effacer l'ancienne allocation de MSFT, pas seulement ajouter GOOG.
    update_allocations(mem_session, 1, [
        {"Ticker": "AAPL", "Broker": "IBKR", "Poids total (%)": 55.0},
        {"Ticker": "GOOG", "Broker": "IBKR", "Poids total (%)": 45.0},
    ])
    rows2 = {r.ticker: r.allocation_pct for r in mem_session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == 1)
    ).all()}
    assert rows2["AAPL"] == 55.0
    assert rows2["GOOG"] == 45.0
    assert rows2["MSFT"] is None  # résidu du run précédent effacé
```

- [ ] **Step 2: Run test to verify it fails or passes for the wrong reason**

Run: `cd backend && uv run pytest tests/test_finance/test_buffett_progressive_allocation.py -v`
Expected: PASS déjà (le comportement `reset=True` existe déjà dans `reporting.py` —
ce test est une garde de non-régression documentant explicitement le contrat dont
la Task 2 dépend). Si ça échoue, ne PAS toucher à `reporting.py` : investiguer
d'abord, c'est un signal que l'hypothèse de la spec est fausse.

- [ ] **Step 3: Regrouper les imports du bloc d'optimisation**

Dans `backend/app/services/finance/buffett/runner.py`, le bloc d'imports actuel
(autour de la ligne 487-494) :

```python
        from .dedup import deduplicate_correlated, deduplicate_tickers
        from .optimizer import optimize_portfolio_de, prepare_optimization
        from .allocation import close_prices_from_download, discretize_allocation, latest_prices
        from .broker_availability import merge_broker_columns
        from .broker_budgets import apply_live_broker_budgets
        import pandas as pd
        import numpy as np
        import yfinance as yf
```

devient :

```python
        from .dedup import deduplicate_correlated, deduplicate_tickers
        from .optimizer import optimize_portfolio_de, prepare_optimization
        from .allocation import close_prices_from_download, discretize_allocation, latest_prices
        from .broker_availability import merge_broker_columns
        from .broker_budgets import apply_live_broker_budgets
        from .reporting import update_allocations
        from . import optimization_progress as opt_prog
        import pandas as pd
        import numpy as np
        import yfinance as yf
```

- [ ] **Step 4: Câbler `on_new_best` + `optimization_progress` autour de l'appel DE**

Dans le même fichier, le bloc actuel (autour de la ligne 561-575) :

```python
                mat_access, active_b = prepare_optimization(t_opt, df_m)
                weights, metric = optimize_portfolio_de(t_opt, rets, mat_access, active_b)
                total_cap = sum(Config.BUDGET_BROKERS.values())
                # Discrétisation : actions entières (hors Trading212) / pies (Trading212)
                prices = latest_prices(cd, t_opt)
                alloc = discretize_allocation(t_opt, weights, active_b, prices, total_cap)
                # Persister les allocations en DB
                if run_id is not None:
                    try:
                        from .reporting import update_allocations
                        with session_factory() as session:
                            update_allocations(session, run_id, alloc)
                        print(f"[runner] Allocations persistees ({len(alloc)} lignes)")
                    except Exception as e:
                        print(f"[runner] Erreur persistance allocations: {e}")
```

devient :

```python
                mat_access, active_b = prepare_optimization(t_opt, df_m)
                total_cap = sum(Config.BUDGET_BROKERS.values())
                # Discrétisation : actions entières (hors Trading212) / pies (Trading212)
                prices = latest_prices(cd, t_opt)

                def _on_new_best(w_matrix) -> None:
                    """Persiste le meilleur portefeuille trouvé jusqu'ici (toutes seeds
                    DE confondues) pendant l'optimisation -- affichage en direct au lieu
                    d'attendre la fin (peut durer des heures)."""
                    if run_id is None:
                        return
                    try:
                        partial_alloc = discretize_allocation(
                            t_opt, w_matrix, active_b, prices, total_cap,
                        )
                        with session_factory() as session:
                            update_allocations(session, run_id, partial_alloc)
                    except Exception as e:
                        print(f"[runner] Erreur allocation progressive: {e}")

                opt_prog.start(run_id=run_id, message="Préparation de l'optimisation…")
                opt_prog.set_phase(
                    "optimisation",
                    f"Optimisation Differential Evolution ({len(t_opt)} titres)…",
                )
                try:
                    weights, metric = optimize_portfolio_de(
                        t_opt, rets, mat_access, active_b,
                        progress_cb=opt_prog.update_de, on_new_best=_on_new_best,
                    )
                finally:
                    opt_prog.finish(message="Optimisation terminée.")

                alloc = discretize_allocation(t_opt, weights, active_b, prices, total_cap)
                # Persister l'allocation finale en DB
                if run_id is not None:
                    try:
                        with session_factory() as session:
                            update_allocations(session, run_id, alloc)
                        print(f"[runner] Allocations persistees ({len(alloc)} lignes)")
                    except Exception as e:
                        print(f"[runner] Erreur persistance allocations: {e}")
```

- [ ] **Step 5: Run the full Buffett test suite**

Run: `cd backend && uv run pytest tests/test_finance/ -v -k buffett or optimizer`
Expected: PASS (tous les tests `test_buffett_*` et `test_optimizer_robust.py`,
y compris ceux de la Task 1)

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/services/finance/buffett/runner.py tests/test_finance/test_buffett_progressive_allocation.py
git commit -m "$(cat <<'EOF'
feat(buffett): progression live pour le run automatique

Cable optimization_progress (deja utilise par le bouton manuel) et le
nouveau callback on_new_best sur le run automatique job_monthly_buffett
-> barre generation/convergence + allocation progressive persistee en
DB pendant la phase d'optimisation DE, qui peut durer des heures sans
retour visuel aujourd'hui.
EOF
)"
```

---

### Task 3 : Frontend — composant partagé `DeProgressBar`

**Files:**
- Modify: `frontend/components/finance/buffett-ui.tsx`
- Modify: `frontend/components/finance/BuffettActionsPanel.tsx`

**Interfaces:**
- Produces: `export type OptProgress` et `export function DeProgressBar({ optProgress: OptProgress | null })` dans `buffett-ui.tsx`, consommés par `BuffettActionsPanel.tsx` (Task 3) et `BuffettTab.tsx` (Task 4).

- [ ] **Step 1: Extraire `OptProgress` et `DeProgressBar` dans `buffett-ui.tsx`**

Dans `frontend/components/finance/buffett-ui.tsx`, ajouter en haut du fichier
(après l'import de `Badge`) et à la fin du fichier :

```tsx
"use client";

/** Petits composants partagés de l'onglet Buffett (extraits de BuffettTab, #532). */

import { financeApi } from "@/lib/finance";
import { Badge } from "@/components/ui/badge";

export function fmt(n?: number, dec = 1) {
  return n != null ? n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : "—";
}

export function StatusBadge({ s }: { s: string }) {
  const map: Record<string, "success" | "warning" | "destructive" | "info"> = {
    termine: "success", en_cours: "info", interrompu: "warning", erreur: "destructive",
  };
  return <Badge variant={map[s] ?? "outline"}>{s}</Badge>;
}

export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full h-2 rounded-full bg-[var(--muted)] overflow-hidden">
      <div className="h-full rounded-full bg-[var(--ring)] bar-fill"
        style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export function ScoreChip({ score }: { score?: number }) {
  if (score == null) return <span className="text-[var(--muted-foreground)]">—</span>;
  const color = score >= 200
    ? "text-[var(--info)]"
    : score >= 80 ? "text-[var(--success)]" : "";
  const label = score >= 200 ? "ETF" : fmt(score);
  return <span className={`font-medium ${color}`}>{label}</span>;
}

/** Progression de l'optimisation Differential Evolution (génération / convergence),
 *  partagée entre le bouton manuel "Créer le portefeuille optimal" et le run
 *  automatique une fois le scoring des tickers terminé. */
export type OptProgress = Awaited<ReturnType<typeof financeApi.portfolioProgress>>;

const PHASE_LABEL: Record<OptProgress["phase"], string> = {
  idle: "",
  preparation: "Préparation…",
  optimisation: "Optimisation (Differential Evolution)…",
  finalisation: "Finalisation…",
};

export function DeProgressBar({ optProgress }: { optProgress: OptProgress | null }) {
  if (!optProgress) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--muted-foreground)]">
          {optProgress.active
            ? (PHASE_LABEL[optProgress.phase] || "En cours…")
            : (optProgress.message || "Terminé")}
          {optProgress.active && optProgress.phase === "optimisation" && optProgress.iteration > 0
            ? ` · génération ${optProgress.iteration}` : ""}
        </span>
        {optProgress.active && optProgress.phase === "optimisation" && (
          <span className="font-mono text-[var(--muted-foreground)]">
            {fmt(optProgress.progress_pct, 0)}%
          </span>
        )}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--muted)]">
        <div
          className={`h-full rounded-full bg-[var(--primary)] transition-[width] duration-500 ${
            optProgress.active && optProgress.phase !== "optimisation" ? "animate-pulse" : ""
          }`}
          style={{
            width: !optProgress.active
              ? "100%"
              : optProgress.phase === "optimisation"
                ? `${Math.max(optProgress.progress_pct, 2)}%`
                : "100%",
          }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `BuffettActionsPanel.tsx` réutilise `DeProgressBar`**

Les imports actuels (lignes 1-18) :

```tsx
"use client";

/** Panneau des 3 actions Buffett : run complet, ticker unique, portefeuille optimal
 *  (extrait de BuffettTab, #532). */

import { useCallback, useEffect, useRef, useState } from "react";
import { financeApi } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip } from "./buffett-ui";

type OptProgress = Awaited<ReturnType<typeof financeApi.portfolioProgress>>;

const PHASE_LABEL: Record<OptProgress["phase"], string> = {
  idle: "",
  preparation: "Préparation…",
  optimisation: "Optimisation (Differential Evolution)…",
  finalisation: "Finalisation…",
};
```

deviennent :

```tsx
"use client";

/** Panneau des 3 actions Buffett : run complet, ticker unique, portefeuille optimal
 *  (extrait de BuffettTab, #532). */

import { useCallback, useEffect, useRef, useState } from "react";
import { financeApi } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, ScoreChip, DeProgressBar, type OptProgress } from "./buffett-ui";
```

Puis le bloc JSX de la barre de progression (fin du fichier, lignes ~181-213) :

```tsx
      {/* Barre de progression de l'optimisation DE */}
      {optProgress && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--muted-foreground)]">
              {optProgress.active
                ? (PHASE_LABEL[optProgress.phase] || "En cours…")
                : (optProgress.message || "Terminé")}
              {optProgress.active && optProgress.phase === "optimisation" && optProgress.iteration > 0
                ? ` · génération ${optProgress.iteration}` : ""}
            </span>
            {optProgress.active && optProgress.phase === "optimisation" && (
              <span className="font-mono text-[var(--muted-foreground)]">
                {fmt(optProgress.progress_pct, 0)}%
              </span>
            )}
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--muted)]">
            <div
              className={`h-full rounded-full bg-[var(--primary)] transition-[width] duration-500 ${
                optProgress.active && optProgress.phase !== "optimisation" ? "animate-pulse" : ""
              }`}
              style={{
                width: !optProgress.active
                  ? "100%"
                  : optProgress.phase === "optimisation"
                    ? `${Math.max(optProgress.progress_pct, 2)}%`
                    : "100%",
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

devient :

```tsx
      {/* Barre de progression de l'optimisation DE */}
      <DeProgressBar optProgress={optProgress} />
    </div>
  );
}
```

- [ ] **Step 3: Vérifier types + lint**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

Run: `cd frontend && npm run lint`
Expected: aucune erreur.

- [ ] **Step 4: Commit**

```bash
cd frontend
git add components/finance/buffett-ui.tsx components/finance/BuffettActionsPanel.tsx
git commit -m "$(cat <<'EOF'
refactor(buffett): extraire DeProgressBar dans buffett-ui.tsx

Extrait la barre generation/convergence du bouton manuel dans un
composant partage, reutilise par le run automatique dans la task
suivante. Pur refactor, aucun changement de comportement.
EOF
)"
```

---

### Task 4 : Frontend — progression live sur le run automatique + vue détail rafraîchie

**Files:**
- Modify: `frontend/components/finance/BuffettTab.tsx`
- Modify: `frontend/components/finance/BuffettRunDetailView.tsx`

**Interfaces:**
- Consumes: `DeProgressBar`, `OptProgress` (Task 3) ; `financeApi.portfolioProgress()`, `financeApi.buffettRun(id)` (existants, `frontend/lib/finance.ts`).

- [ ] **Step 1: `BuffettTab.tsx` — importer `DeProgressBar`**

Import actuel (ligne 14) :

```tsx
import { fmt, ProgressBar, StatusBadge } from "./buffett-ui";
```

devient :

```tsx
import { fmt, ProgressBar, StatusBadge, DeProgressBar, type OptProgress } from "./buffett-ui";
```

- [ ] **Step 2: Ajouter l'état et le polling de la phase d'optimisation**

L'état actuel (lignes 19-26) :

```tsx
  const [runs, setRuns] = useState<BuffettRunOut[]>([]);
  const [selected, setSelected] = useState<BuffettRunDetail | null>(null);
  const [progress, setProgress] = useState<BuffettProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

devient :

```tsx
  const [runs, setRuns] = useState<BuffettRunOut[]>([]);
  const [selected, setSelected] = useState<BuffettRunDetail | null>(null);
  const [progress, setProgress] = useState<BuffettProgress | null>(null);
  const [optProgress, setOptProgress] = useState<OptProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const optPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

Juste après le `useEffect` existant qui sonde `/buffett/progress` (après la ligne
`}, [progress?.active, loadRuns]);`, ajouter :

```tsx
  const stopOptPolling = useCallback(() => {
    if (optPollRef.current) { clearInterval(optPollRef.current); optPollRef.current = null; }
  }, []);

  const pollOptProgress = useCallback(async (runId: number) => {
    const p = await financeApi.portfolioProgress().catch(() => null);
    if (p && p.run_id === runId) {
      setOptProgress(p);
      if (!p.active) stopOptPolling();
    } else if (!p?.active) {
      stopOptPolling();
    }
  }, [stopOptPolling]);

  // Une fois le scoring des tickers à 100 %, le run automatique enchaîne sur la
  // phase d'optimisation DE (peut durer des heures) : on relaie la même barre de
  // progression que le bouton manuel "Créer le portefeuille optimal".
  useEffect(() => {
    const runId = progress?.run_id;
    const scoringDone = (progress?.progress_pct ?? 0) >= 100;
    if (progress?.active && scoringDone && runId != null) {
      stopOptPolling();
      pollOptProgress(runId);
      optPollRef.current = setInterval(() => pollOptProgress(runId), 3000);
    } else {
      stopOptPolling();
      setOptProgress(null);
    }
    return () => stopOptPolling();
  }, [progress?.active, progress?.progress_pct, progress?.run_id, pollOptProgress, stopOptPolling]);

  // Rafraîchit le détail d'un run "en_cours" pour afficher l'allocation
  // progressive (meilleur portefeuille trouvé jusqu'ici) sans action utilisateur.
  useEffect(() => {
    if (!selected || selected.run.statut !== "en_cours") return;
    const id = selected.run.id;
    const iv = setInterval(async () => {
      const fresh = await financeApi.buffettRun(id).catch(() => null);
      if (fresh) setSelected(fresh);
    }, 5000);
    return () => clearInterval(iv);
  }, [selected?.run.id, selected?.run.statut]);
```

- [ ] **Step 3: Afficher `DeProgressBar` dans la carte de progression**

Le bloc JSX actuel (lignes ~121-154) :

```tsx
      {/* Progression (active) ou reprise (interrompue) */}
      {(progress?.active || interrupted) && (
        <div className={`rounded-[var(--radius-lg)] border p-4 space-y-2 ${
          interrupted ? "border-[var(--warning-muted)] bg-[var(--warning-muted)]" : "border-[var(--border)]"}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              {interrupted
                ? "⏸ Analyse interrompue"
                : paused
                  ? "⏳ En pause (limite API atteinte)"
                  : "Analyse en cours..."}
            </span>
            <Badge variant={interrupted || paused ? "warning" : "info"}>{fmt(progress?.progress_pct)}%</Badge>
          </div>
          <ProgressBar pct={progress?.progress_pct ?? 0} />
          {progress?.n_done != null && progress?.n_total != null && (
            <p className="text-xs text-[var(--muted-foreground)]">
              {progress.n_done} / {progress.n_total} tickers analysés
            </p>
          )}
          {paused && (
```

devient :

```tsx
      {/* Progression (active) ou reprise (interrompue) */}
      {(progress?.active || interrupted) && (
        <div className={`rounded-[var(--radius-lg)] border p-4 space-y-2 ${
          interrupted ? "border-[var(--warning-muted)] bg-[var(--warning-muted)]" : "border-[var(--border)]"}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              {interrupted
                ? "⏸ Analyse interrompue"
                : paused
                  ? "⏳ En pause (limite API atteinte)"
                  : optProgress?.active
                    ? "Scoring terminé — optimisation du portefeuille en cours..."
                    : "Analyse en cours..."}
            </span>
            <Badge variant={interrupted || paused ? "warning" : "info"}>{fmt(progress?.progress_pct)}%</Badge>
          </div>
          <ProgressBar pct={progress?.progress_pct ?? 0} />
          {progress?.n_done != null && progress?.n_total != null && (
            <p className="text-xs text-[var(--muted-foreground)]">
              {progress.n_done} / {progress.n_total} tickers analysés
            </p>
          )}
          <DeProgressBar optProgress={optProgress} />
          {paused && (
```

- [ ] **Step 4: `BuffettRunDetailView.tsx` — bandeau "optimisation en cours"**

Le bloc actuel (lignes 102-122) :

```tsx
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack}>← Retour</Button>
        <h2 className="text-base font-semibold">Run du {selected.run.run_date}</h2>
        <StatusBadge s={selected.run.statut} />
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={runBacktest} loading={backtesting}>
            📈 Backtest 2 ans
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => exportRun(selected.run.id, selected.run.run_date, "xlsx")}>
            📊 Excel
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => exportRun(selected.run.id, selected.run.run_date, "csv")}>
            📄 CSV
          </Button>
        </div>
      </div>
      {backtest && (
```

devient :

```tsx
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack}>← Retour</Button>
        <h2 className="text-base font-semibold">Run du {selected.run.run_date}</h2>
        <StatusBadge s={selected.run.statut} />
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={runBacktest} loading={backtesting}>
            📈 Backtest 2 ans
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => exportRun(selected.run.id, selected.run.run_date, "xlsx")}>
            📊 Excel
          </Button>
          <Button variant="outline" size="sm"
            onClick={() => exportRun(selected.run.id, selected.run.run_date, "csv")}>
            📄 CSV
          </Button>
        </div>
      </div>
      {selected.run.statut === "en_cours" && (
        <p className="text-xs rounded-[var(--radius)] bg-[var(--info-muted)] text-[var(--info-foreground)] px-3 py-2">
          🔄 Optimisation en cours — ce portefeuille s&apos;améliore en direct, actualisation automatique.
        </p>
      )}
      {backtest && (
```

- [ ] **Step 5: Vérifier types + lint**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

Run: `cd frontend && npm run lint`
Expected: aucune erreur.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add components/finance/BuffettTab.tsx components/finance/BuffettRunDetailView.tsx
git commit -m "$(cat <<'EOF'
feat(buffett): affichage live de l'optimisation sur le run automatique

BuffettTab bascule sur la barre generation/convergence une fois le
scoring des tickers a 100%. La vue detail d'un run "en_cours" se
rafraichit automatiquement (5s) et affiche un bandeau explicite au
lieu de traiter l'allocation comme definitive.
EOF
)"
```

---

### Task 5 : Vérification end-to-end manuelle

**Files:** aucun (validation, pas de code).

- [ ] **Step 1: Réduire temporairement les paramètres DE pour un test rapide**

Dans `backend/app/services/finance/buffett/config.py`, noter les valeurs actuelles
de `STARR_DE_N_SEEDS` (10), `STARR_DE_MIN_GENERATIONS` (30) — ne PAS committer de
changement ici, juste éditer localement le temps du test, ou définir les variables
d'env correspondantes si `Config.load_params()` les supporte (vérifier
`backend/app/services/finance/buffett/config.py`). Objectif : un run complet en
quelques minutes au lieu de plusieurs heures.

- [ ] **Step 2: Lancer l'app et déclencher un run complet**

Suivre le script de démarrage habituel du projet (backend + frontend). Depuis
l'onglet Finance → Buffett, cliquer « Lancer » (bouton 1).

- [ ] **Step 3: Observer le scoring puis la bascule vers l'optimisation**

Attendre que la barre de progression du scoring atteigne 100 %. Vérifier que le
libellé bascule sur « Scoring terminé — optimisation du portefeuille en cours... »
et qu'une seconde barre (génération / convergence) apparaît en dessous.

- [ ] **Step 4: Ouvrir le détail du run en cours**

Cliquer sur le run actif dans l'historique. Vérifier :
- le bandeau « 🔄 Optimisation en cours… » est visible,
- une allocation cible s'affiche (pas de tableau vide),
- en revenant sur l'écran quelques secondes plus tard (ou en laissant la page
  ouverte), l'allocation change au moins une fois avant la fin du run — signe que
  la mise à jour progressive fonctionne.

- [ ] **Step 5: Vérifier la fin du run**

Une fois le run terminé (`statut: "termine"`), vérifier que le bandeau
« optimisation en cours » disparaît et que l'allocation affichée correspond au
dernier message `[runner] Allocations persistees (...)` des logs backend.

- [ ] **Step 6: Restaurer la config DE si modifiée localement**

Si `config.py` a été édité pour le test (Step 1), `git diff` doit être vide sur ce
fichier avant de continuer — sinon `git checkout -- backend/app/services/finance/buffett/config.py`.
