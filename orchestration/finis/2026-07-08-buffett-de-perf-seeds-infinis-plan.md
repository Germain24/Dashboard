# Buffett DE : perf + seeds infinis avec arrêt manuel — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Éliminer le ralentissement progressif de l'optimisation DE (WAL SQLite + écriture synchrone) et remplacer le budget fixe de 10 seeds par une boucle illimitée avec bouton d'arrêt manuel, sur les deux points d'entrée (run automatique + bouton manuel).

**Architecture:** `optimize_portfolio_de` reçoit un nouveau paramètre `should_stop` (vérifié entre deux seeds, jamais au milieu) et rapporte désormais `(seed_num, iteration, convergence)` à `progress_cb` au lieu de `(iteration, convergence)`. `optimization_progress.py` expose `seed_num` et `stop_requested`/`request_stop()`. Un nouvel endpoint `POST /finance/buffett/optimization/stop` positionne ce flag, consommé par les deux appelants (`runner.py`, `buffett.py`). L'écriture progressive de l'allocation (`_on_new_best` dans `runner.py`) part dans un thread daemon avec verrou non-bloquant pour ne plus jamais bloquer la boucle DE. SQLite checkpoint automatiquement plus souvent (`wal_autocheckpoint`).

**Tech Stack:** Python (FastAPI, SQLModel, scipy.optimize, threading), pytest, Next.js/React (TypeScript).

## Global Constraints

- L'arrêt (`should_stop`) n'est **jamais** vérifié au milieu d'un seed — uniquement entre deux seeds, pour qu'un seed interrompu ne compte jamais dans les statistiques de robustesse inter-seeds.
- Sans `should_stop` fourni, `optimize_portfolio_de` s'arrête après **exactement 1 seed** (comportement par défaut sûr — remplace l'ancien `Config.STARR_DE_N_SEEDS`, sans risque de boucle infinie pour les appelants/tests qui ne gèrent pas l'arrêt).
- Après un arrêt manuel, le run passe à `statut = "termine"` comme une convergence naturelle — **aucun nouveau statut**.
- `rng=seed + k` (déjà en place) garantit que chaque seed explore un point de départ distinct, y compris en boucle illimitée — aucun changement nécessaire sur ce point.
- Spec source : `orchestration/a-faire/2026-07-08-buffett-de-perf-seeds-infinis-design.md`.

---

### Task 1 : Checkpoint WAL automatique

**Files:**
- Modify: `backend/app/core/db.py`

**Interfaces:**
- Aucune nouvelle interface publique — configuration de connexion uniquement.

- [ ] **Step 1: Ajouter le PRAGMA `wal_autocheckpoint`**

Dans `backend/app/core/db.py`, le bloc actuel :

```python
if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _conn_record) -> None:
        """WAL + busy_timeout : réduit les "database is locked" quand les jobs
        APScheduler écrivent en même temps que les requêtes HTTP."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")  # attend jusqu'à 5 s un verrou
        cur.execute("PRAGMA synchronous=NORMAL")  # bon compromis durabilité/perf en WAL
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
```

devient :

```python
if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _conn_record) -> None:
        """WAL + busy_timeout : réduit les "database is locked" quand les jobs
        APScheduler écrivent en même temps que les requêtes HTTP."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")  # attend jusqu'à 5 s un verrou
        cur.execute("PRAGMA synchronous=NORMAL")  # bon compromis durabilité/perf en WAL
        cur.execute("PRAGMA foreign_keys=ON")
        # Checkpoint automatique tous les 200 pages (~800 Ko) au lieu du défaut
        # ~1000 : sur un run Buffett de plusieurs heures qui écrit en continu
        # (progression DE), un WAL qui grossit sans être purgé dégrade
        # progressivement chaque lecture/écriture SQLite (mesuré : 815 pages/
        # ~3,2 Mo non checkpointées après quelques heures -> ralentissement 7x).
        cur.execute("PRAGMA wal_autocheckpoint=200")
        cur.close()
```

- [ ] **Step 2: Write a test verifying the pragma is applied**

`_sqlite_pragmas` dans `app/core/db.py` est un event listener enregistré sur un engine spécifique
(`@event.listens_for(engine, "connect")`) — le test l'appelle directement avec une connexion
sqlite3 brute plutôt que de recréer un engine SQLAlchemy séparé, plus simple et plus direct :

```python
# backend/tests/test_finance/test_db_pragmas.py
"""Le WAL SQLite doit checkpointer automatiquement plus souvent que le defaut
(~1000 pages) pour eviter le ralentissement progressif observe sur un run
Buffett de plusieurs heures (voir orchestration/a-faire/2026-07-08-buffett-de-
perf-seeds-infinis-design.md)."""

import sqlite3

from app.core.db import _sqlite_pragmas


def test_wal_autocheckpoint_is_lowered(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(str(db_path))
    try:
        _sqlite_pragmas(con, None)
        value = con.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
        assert int(value) == 200
    finally:
        con.close()
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_finance/test_db_pragmas.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd backend
git add app/core/db.py tests/test_finance/test_db_pragmas.py
git commit -m "$(cat <<'EOF'
perf(db): checkpoint WAL SQLite plus frequent (200 pages)

Le WAL grossissait sans etre purge assez souvent sur un run Buffett de
plusieurs heures (mesure : 815 pages/~3.2Mo en attente), degradant
progressivement chaque lecture/ecriture SQLite -> ralentissement 7x
mesure de la boucle DE (0.4s/generation -> 2.9s/generation).
EOF
)"
```

---

### Task 2 : `optimization_progress.py` — seed_num + arrêt manuel

**Files:**
- Modify: `backend/app/services/finance/buffett/optimization_progress.py`
- Modify: `backend/tests/test_finance/test_optimization_progress.py`

**Interfaces:**
- Produces: `update_de(seed_num: int, iteration: int, convergence: float) -> None` (signature étendue), `request_stop() -> None`, `snapshot()` renvoie désormais aussi `seed_num: int` et `stop_requested: bool`. Consommé par Task 3 (optimizer.py, via le paramètre `progress_cb` passé par les appelants) et Task 4/5 (runner.py/buffett.py, via `should_stop=lambda: opt_prog.snapshot()["stop_requested"]`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_finance/test_optimization_progress.py — ajouter à la fin du fichier

def test_update_de_tracks_seed_num():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    op.start(run_id=1)
    op.update_de(seed_num=1, iteration=5, convergence=0.1)
    assert op.snapshot()["seed_num"] == 1
    op.update_de(seed_num=4, iteration=12, convergence=0.3)
    assert op.snapshot()["seed_num"] == 4
    assert op.snapshot()["iteration"] == 12
    op.reset()


def test_request_stop_sets_flag_reset_by_start():
    from app.services.finance.buffett import optimization_progress as op

    op.reset()
    assert op.snapshot()["stop_requested"] is False
    op.request_stop()
    assert op.snapshot()["stop_requested"] is True
    # Un nouveau start() (nouveau run) doit remettre le flag a zero.
    op.start(run_id=2)
    assert op.snapshot()["stop_requested"] is False
    op.reset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_finance/test_optimization_progress.py::test_update_de_tracks_seed_num -v`
Expected: FAIL with `TypeError: update_de() missing 1 required positional argument: 'iteration'` (ou équivalent — `seed_num` n'est pas encore un paramètre reconnu)

- [ ] **Step 3: Étendre le module**

Dans `backend/app/services/finance/buffett/optimization_progress.py`, le fichier actuel :

```python
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
```

devient :

```python
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
}


def reset() -> None:
    with _lock:
        _state.update(active=False, phase="idle", seed_num=0, iteration=0,
                      convergence=0.0, message="", run_id=None, stop_requested=False)


def start(run_id: int | None = None, message: str = "") -> None:
    with _lock:
        _state.update(active=True, phase="preparation", seed_num=0, iteration=0,
                      convergence=0.0, message=message, run_id=run_id, stop_requested=False)


def set_phase(phase: str, message: str = "") -> None:
    with _lock:
        _state["phase"] = phase
        if message:
            _state["message"] = message


def update_de(seed_num: int, iteration: int, convergence: float) -> None:
    """Mise à jour pendant le Differential Evolution (1 appel par génération).

    ``seed_num`` : numéro du seed en cours (1-indexé, augmente à chaque
    redémarrage du DE). ``iteration`` : génération dans CE seed (repart de 1 à
    chaque nouveau seed)."""
    with _lock:
        _state["phase"] = "optimisation"
        _state["seed_num"] = int(seed_num)
        _state["iteration"] = int(iteration)
        _state["convergence"] = max(0.0, min(float(convergence), 1.0))


def request_stop() -> None:
    """Demande l'arrêt de l'optimisation en cours -- pris en compte à la fin du
    seed en cours (jamais au milieu), par les deux points d'entrée DE (run
    automatique et bouton manuel « Créer le portefeuille optimal »)."""
    with _lock:
        _state["stop_requested"] = True


def finish(message: str = "") -> None:
    with _lock:
        _state.update(active=False, phase="idle", convergence=1.0, message=message)
```

- [ ] **Step 4: Mettre à jour le test existant qui appelle `update_de` avec l'ancienne signature**

Dans `backend/tests/test_finance/test_optimization_progress.py`, le test actuel (lignes ~19-23) :

```python
    op.update_de(iteration=3, convergence=0.4)
    s = op.snapshot()
    assert s["iteration"] == 3
    assert abs(s["convergence"] - 0.4) < 1e-9
    assert s["phase"] == "optimisation"
```

devient :

```python
    op.update_de(seed_num=1, iteration=3, convergence=0.4)
    s = op.snapshot()
    assert s["seed_num"] == 1
    assert s["iteration"] == 3
    assert abs(s["convergence"] - 0.4) < 1e-9
    assert s["phase"] == "optimisation"
```

Et dans `test_optimization_progress_convergence_clamped_0_1`, les deux appels actuels :

```python
    op.update_de(iteration=1, convergence=5.0)  # scipy peut dépasser 1
    assert op.snapshot()["convergence"] == 1.0
    op.update_de(iteration=2, convergence=-0.2)
    assert op.snapshot()["convergence"] == 0.0
```

deviennent :

```python
    op.update_de(seed_num=1, iteration=1, convergence=5.0)  # scipy peut dépasser 1
    assert op.snapshot()["convergence"] == 1.0
    op.update_de(seed_num=1, iteration=2, convergence=-0.2)
    assert op.snapshot()["convergence"] == 0.0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_finance/test_optimization_progress.py -v`
Expected: PASS (les 2 tests existants adaptés + les 2 nouveaux du Step 1). La 3e fonction du
fichier (`test_optimize_portfolio_de_reports_progress`) va encore échouer à ce stade — normal,
elle est corrigée dans la Task 3 (elle teste `optimize_portfolio_de`, pas ce module).

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/services/finance/buffett/optimization_progress.py tests/test_finance/test_optimization_progress.py
git commit -m "$(cat <<'EOF'
feat(buffett): seed_num + arret manuel dans optimization_progress

update_de() rapporte desormais le numero de seed en cours (1-indexe)
en plus de la generation. Nouveau request_stop()/stop_requested,
remis a zero par start() -- consomme par les deux points d'entree DE
pour le bouton d'arret manuel.
EOF
)"
```

---

### Task 3 : `optimizer.py` — seeds illimités + `should_stop` + plafond relevé

**Files:**
- Modify: `backend/app/services/finance/buffett/optimizer.py`
- Modify: `backend/app/services/finance/buffett/config.py`
- Modify: `backend/tests/test_finance/test_optimizer_robust.py`
- Modify: `backend/tests/test_finance/test_optimization_progress.py`

**Interfaces:**
- Consumes: rien de nouveau des tasks précédentes (indépendant de Task 2 côté code — juste besoin que l'appelant du test utilise le nouveau contrat `progress_cb(seed_num, iteration, convergence)`).
- Produces: `optimize_portfolio_de(..., should_stop: Callable[[], bool] | None = None)`. Sans `should_stop`, s'arrête après 1 seed. Avec, continue tant que `should_stop()` renvoie `False`, vérifié uniquement entre deux seeds. `progress_cb` est maintenant appelé `progress_cb(seed_num, iteration, convergence)` (3 arguments, `iteration` remis à 1 à chaque nouveau seed). Consommé par Task 4 (`runner.py`) et Task 5 (`buffett.py`).

- [ ] **Step 1: Write the failing test — arrêt après le nombre de seeds voulu**

```python
# backend/tests/test_finance/test_optimizer_robust.py — ajouter à la fin du fichier

def test_de_stops_after_should_stop_true(monkeypatch):
    """should_stop() verifie uniquement ENTRE deux seeds : avec should_stop qui
    renvoie True des le debut, on ne fait qu'UN SEUL seed puis on s'arrete."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(3)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    seeds_seen: set[int] = set()
    W, starr = optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv: seeds_seen.add(seed_num),
        should_stop=lambda: True,
    )
    assert seeds_seen == {1}   # un seul seed a tourne
    assert np.isfinite(W).all()
    assert abs(W.sum() - 1.0) < 1e-6


def test_de_without_should_stop_runs_exactly_one_seed(monkeypatch):
    """Sans should_stop (defaut None) : exactement 1 seed, jamais de boucle
    infinie -- comportement sur qui remplace l'ancien STARR_DE_N_SEEDS=1 des
    tests existants."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(4)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    seeds_seen: set[int] = set()
    optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv: seeds_seen.add(seed_num),
    )
    assert seeds_seen == {1}


def test_de_continues_past_first_seed_when_not_stopped(monkeypatch):
    """should_stop qui renvoie False les 2 premieres fois puis True : verifie
    qu'on fait bien plusieurs seeds avant de s'arreter (pas bloque au 1er)."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(5)
    n = 10
    R = rng.normal(0.0006, 0.02, (500, n))
    rets = pd.DataFrame(R, columns=[f"T{i}" for i in range(n)])
    access = [[True] for _ in range(n)]

    calls = {"n": 0}
    def should_stop():
        calls["n"] += 1
        return calls["n"] >= 3   # False, False, True -> 3 seeds

    seeds_seen: set[int] = set()
    optimize_portfolio_de(
        list(rets.columns), rets, access, ["IBKR"], n_sim=3000,
        progress_cb=lambda seed_num, it, conv: seeds_seen.add(seed_num),
        should_stop=should_stop,
    )
    assert seeds_seen == {1, 2, 3}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_finance/test_optimizer_robust.py -k should_stop -v`
Expected: FAIL — `optimize_portfolio_de() got an unexpected keyword argument 'should_stop'`

- [ ] **Step 3: Bump `STARR_DE_MAX_GENERATIONS`, retirer `STARR_DE_N_SEEDS`**

Dans `backend/app/services/finance/buffett/config.py`, le bloc actuel (lignes ~67-87) :

```python
    # Arrêt du Differential Evolution : PAS de plafond de générations comme critère
    # normal — le DE s'arrête quand sa population converge (écart-type des scores
    # <= tol, cf. DifferentialEvolutionSolver.converged()), avec un minimum de
    # générations pour éviter une convergence prématurée (population encore peu
    # diversifiée après quelques générations seulement). STARR_DE_MAX_GENERATIONS
    # n'est qu'un garde-fou anti-boucle-infinie ; s'il est atteint, c'est loggé
    # comme une anomalie (le DE n'a pas convergé naturellement).
    STARR_DE_MIN_GENERATIONS: int = 30
    STARR_DE_MAX_GENERATIONS: int = 2000
    # Tolérance de convergence (écart-type des scores de la population / |moyenne|
    # <= tol). Choix délibéré de garder 1e-6 (précision maximale) malgré le coût :
    # sur un cas de test à 29 titres, la convergence naturelle demande ~730
    # générations (~144s/seed) — cf. STARR_DE_N_SEEDS ci-dessous pour le budget total.
    STARR_DE_TOL: float = 1e-6
    # Nombre de redémarrages (seeds différentes) du DE : sert à vérifier qu'on ne
    # retombe pas sur un optimum local isolé — si les seeds convergent vers des
    # scores très proches, c'est un plateau robuste ; si ça varie fort, le paysage
    # a plusieurs optima locaux comparables (on garde alors le meilleur des N).
    # 10 seeds x tol=1e-6 (~144s/seed) ≈ 24 min rien que pour le DE (avant polish
    # et le reste du pipeline) — coût assumé pour maximiser la confiance robustesse.
    STARR_DE_N_SEEDS: int = 10
    # Budget d'itérations du polish local gradient-free (Nelder-Mead) en fin de DE.
    STARR_DE_POLISH_MAXITER: int = 300
```

devient :

```python
    # Arrêt du Differential Evolution : PAS de plafond de générations comme critère
    # normal — le DE s'arrête quand sa population converge (écart-type des scores
    # <= tol, cf. DifferentialEvolutionSolver.converged()), avec un minimum de
    # générations pour éviter une convergence prématurée (population encore peu
    # diversifiée après quelques générations seulement). STARR_DE_MAX_GENERATIONS
    # n'est qu'un garde-fou anti-boucle-infinie (paysage pathologique qui ne
    # convergerait jamais) ; s'il est atteint, c'est loggé comme une anomalie.
    # Relevé à 50 000 (au lieu de 2000) pour rester purement défensif : jamais le
    # critère d'arrêt normal en pratique.
    STARR_DE_MIN_GENERATIONS: int = 30
    STARR_DE_MAX_GENERATIONS: int = 50_000
    # Tolérance de convergence (écart-type des scores de la population / |moyenne|
    # <= tol). Choix délibéré de garder 1e-6 (précision maximale) malgré le coût :
    # sur un cas de test à 29 titres, la convergence naturelle demande ~730
    # générations (~144s/seed).
    STARR_DE_TOL: float = 1e-6
    # Budget d'itérations du polish local gradient-free (Nelder-Mead) en fin de DE.
    STARR_DE_POLISH_MAXITER: int = 300
```

(Le nombre de seeds n'est plus une constante de config — `optimize_portfolio_de` tourne en boucle
illimitée, arrêtée via le paramètre `should_stop`, cf. Step 4.)

- [ ] **Step 4: Étendre la signature + boucle illimitée + `_report` avec seed_num**

Dans `backend/app/services/finance/buffett/optimizer.py`, la signature actuelle (ligne ~341) :

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

devient :

```python
def optimize_portfolio_de(
    tickers: list[str],
    returns,          # pd.DataFrame de rendements journaliers
    matrix_access: list,
    active_brokers: list[str],
    seed: int = 42,
    progress_cb=None,   # callable(seed_num:int, iteration:int, convergence:float) | None
    on_new_best=None,   # callable(W: np.ndarray[n_tickers x n_brokers]) | None
    should_stop=None,   # callable() -> bool | None -- verifie ENTRE deux seeds seulement.
                         # Sans callback : s'arrete apres exactement 1 seed (defaut sur).
    n_sim: int | None = None,
    alpha: float | None = None,
    downside_weight: float | None = None,
    min_position: float | None = None,
) -> tuple[np.ndarray, float]:
```

Le bloc `_report`/`min_gen`/`max_gen`/`n_seeds` actuel (lignes ~458-471) :

```python
    _iter = {"n": 0}

    def _report(convergence: float) -> None:
        _iter["n"] += 1
        if progress_cb is not None:
            try:
                progress_cb(_iter["n"], float(convergence))
            except Exception:
                pass  # la progression ne doit jamais casser l'optimisation

    min_gen = int(Config.STARR_DE_MIN_GENERATIONS)
    max_gen = int(Config.STARR_DE_MAX_GENERATIONS)   # garde-fou, pas l'arrêt normal
    n_seeds = max(1, int(Config.STARR_DE_N_SEEDS))
    de_tol = float(Config.STARR_DE_TOL)
```

devient :

```python
    def _report(seed_num: int, iteration: int, convergence: float) -> None:
        if progress_cb is not None:
            try:
                progress_cb(seed_num, iteration, float(convergence))
            except Exception:
                pass  # la progression ne doit jamais casser l'optimisation

    min_gen = int(Config.STARR_DE_MIN_GENERATIONS)
    max_gen = int(Config.STARR_DE_MAX_GENERATIONS)   # garde-fou, pas l'arrêt normal
    de_tol = float(Config.STARR_DE_TOL)
```

- [ ] **Step 5: Boucle de seeds illimitée**

Le commentaire + boucle actuels (lignes ~509-518) :

```python
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

devient :

```python
    global_best_energy = float("inf")   # partagé entre TOUS les seeds (jamais remis à zéro)

    # ── Seeds illimités : chaque nouveau départ (rng=seed+k, toujours distinct)
    # explore le paysage différemment. On garde le meilleur de tous les seeds
    # faits et on logge l'écart entre elles (mesure de robustesse : si les
    # scores divergent fort d'un seed à l'autre, le paysage a plusieurs optima
    # locaux comparables). S'arrête quand should_stop() renvoie True, vérifié
    # UNIQUEMENT entre deux seeds (jamais au milieu) -- un seed interrompu ne
    # doit jamais compter dans les stats de robustesse. Sans should_stop : 1
    # seul seed (comportement par défaut sûr, jamais de boucle infinie).
    runs = []   # (energie, x, nit, convergence_naturelle)
    k = 0
    while True:
```

Puis le corps de la boucle (lignes ~519-545, `solver = DifferentialEvolutionSolver(...)` jusqu'à
`runs.append(...)`) : remplacer `rng=seed + k,` (inchangé) et `_report(solver.convergence)` par
`_report(k + 1, nit, solver.convergence)` :

```python
        solver = DifferentialEvolutionSolver(
            neg_obj,
            bounds=bounds,
            rng=seed + k,
            maxiter=max_gen,
            tol=de_tol,
            mutation=(0.5, 1.5),
            recombination=0.9,
            popsize=12,
            polish=False,      # CVaR non lisse -> pas de polish gradient ici (fait après, cf. plus bas)
            workers=1,
            updating="deferred",
        )
        nit = 0
        converged_naturally = False
        for _ in solver:
            nit += 1
            _report(k + 1, nit, solver.convergence)
            if solver.population_energies[0] < global_best_energy:
                global_best_energy = float(solver.population_energies[0])
                _maybe_emit_progress(solver.x)
            if nit >= min_gen and solver.converged():
                converged_naturally = True
                break
            if nit >= max_gen:
                break
        runs.append((float(solver.population_energies[0]), solver.x.copy(), nit, converged_naturally))
        k += 1
        if should_stop is None or should_stop():
            break
```

Puis, juste après la boucle, le print récapitulatif (ligne ~551) :

```python
    print(f"    * DE multi-seed ({n_seeds} depart(s)) : energies={[round(e, 4) for e in energies]}, "
```

devient :

```python
    print(f"    * DE multi-seed ({len(runs)} depart(s)) : energies={[round(e, 4) for e in energies]}, "
```

- [ ] **Step 6: Run new tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_finance/test_optimizer_robust.py -k should_stop -v`
Expected: PASS (3 nouveaux tests)

- [ ] **Step 7: Retirer les 3 lignes `monkeypatch.setattr(Config, "STARR_DE_N_SEEDS", 1)`**

Dans `backend/tests/test_finance/test_optimizer_robust.py`, retirer la ligne
`monkeypatch.setattr(Config, "STARR_DE_N_SEEDS", 1)` dans **chacun** de ces 3 tests (elle n'existe
plus dans `Config`, et n'est plus nécessaire : sans `should_stop`, `optimize_portfolio_de` s'arrête
déjà après exactement 1 seed) :
- `test_de_returns_feasible_finite_weights`
- `test_de_calls_on_new_best_with_decreasing_energy`
- `test_de_without_on_new_best_is_unaffected`

- [ ] **Step 8: Corriger `test_optimize_portfolio_de_reports_progress` (nouveau contrat `progress_cb`)**

Dans `backend/tests/test_finance/test_optimization_progress.py`, le test actuel :

```python
def test_optimize_portfolio_de_reports_progress(monkeypatch):
    """optimize_portfolio_de doit appeler progress_cb(iteration, convergence)
    à chaque génération du Differential Evolution."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    # Réglages DE allégés pour le test (la prod utilise tol=1e-6 et 10 seeds).
    monkeypatch.setattr(Config, "STARR_DE_N_SEEDS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, (300, 3)), columns=["A", "B", "C"])
    matrix = [[True], [True], [True]]

    calls: list[tuple[int, float]] = []
    weights, sharpe = optimize_portfolio_de(
        ["A", "B", "C"], rets, matrix, ["IBKR"], n_sim=2000,
        progress_cb=lambda it, conv: calls.append((it, conv)),
    )
    assert len(calls) > 0
    # itérations strictement croissantes
    iters = [c[0] for c in calls]
    assert iters == sorted(iters)
    assert weights.shape == (3, 1)
```

devient :

```python
def test_optimize_portfolio_de_reports_progress(monkeypatch):
    """optimize_portfolio_de doit appeler progress_cb(seed_num, iteration,
    convergence) à chaque génération du Differential Evolution."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    # Reglages DE allegés pour le test (la prod utilise tol=1e-6). Pas de
    # should_stop -> exactement 1 seed (comportement par defaut).
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-3)
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0.001, 0.02, (300, 3)), columns=["A", "B", "C"])
    matrix = [[True], [True], [True]]

    calls: list[tuple[int, int, float]] = []
    weights, sharpe = optimize_portfolio_de(
        ["A", "B", "C"], rets, matrix, ["IBKR"], n_sim=2000,
        progress_cb=lambda seed_num, it, conv: calls.append((seed_num, it, conv)),
    )
    assert len(calls) > 0
    assert all(c[0] == 1 for c in calls)   # un seul seed
    # itérations (dans ce seed) strictement croissantes
    iters = [c[1] for c in calls]
    assert iters == sorted(iters)
    assert weights.shape == (3, 1)
```

- [ ] **Step 9: Run the full test slice**

Run: `cd backend && uv run pytest tests/test_finance/test_optimizer_robust.py tests/test_finance/test_optimization_progress.py -v`
Expected: PASS (tous les tests des deux fichiers)

- [ ] **Step 10: Commit**

```bash
cd backend
git add app/services/finance/buffett/optimizer.py app/services/finance/buffett/config.py tests/test_finance/test_optimizer_robust.py tests/test_finance/test_optimization_progress.py
git commit -m "$(cat <<'EOF'
feat(buffett): seeds DE illimites (should_stop) + plafond generations releve

optimize_portfolio_de tourne desormais en boucle illimitee de seeds,
arretee via should_stop() verifie UNIQUEMENT entre deux seeds (jamais
au milieu). Sans should_stop : 1 seul seed (defaut sur, remplace
Config.STARR_DE_N_SEEDS qui est retire). progress_cb rapporte
maintenant (seed_num, iteration, convergence) au lieu de
(iteration, convergence). STARR_DE_MAX_GENERATIONS : 2000 -> 50000
(garde-fou pur, jamais le critere d'arret normal).
EOF
)"
```

---

### Task 4 : `runner.py` — écriture asynchrone + `should_stop`

**Files:**
- Modify: `backend/app/services/finance/buffett/runner.py`

**Interfaces:**
- Consumes: `optimize_portfolio_de(..., should_stop=...)` (Task 3), `optimization_progress.snapshot()["stop_requested"]` (Task 2).
- Produces: rien de nouveau — glue interne à `run_buffett_analysis`.

- [ ] **Step 1: Écriture asynchrone dans `_on_new_best` + `should_stop`**

Dans `backend/app/services/finance/buffett/runner.py`, le bloc actuel (autour de la ligne 568-594) :

```python
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
```

devient :

```python
                _write_lock = threading.Lock()

                def _on_new_best(w_matrix) -> None:
                    """Persiste le meilleur portefeuille trouvé jusqu'ici (toutes seeds
                    DE confondues) pendant l'optimisation -- affichage en direct au lieu
                    d'attendre la fin (peut durer des heures). Écriture DB dans un
                    thread séparé : ne bloque JAMAIS la boucle DE (avant ce correctif,
                    une écriture synchrone ici ralentissait progressivement chaque
                    génération à mesure que le WAL SQLite grossissait -- mesuré : 0.4s
                    -> 2.9s/génération sur plusieurs heures). Si une écriture précédente
                    est encore en cours, on ignore ce nouveau meilleur (la suivante,
                    quand elle arrivera, écrira de toute façon un état plus récent)."""
                    if run_id is None:
                        return
                    if not _write_lock.acquire(blocking=False):
                        return

                    def _write() -> None:
                        try:
                            partial_alloc = discretize_allocation(
                                t_opt, w_matrix, active_b, prices, total_cap,
                            )
                            with session_factory() as session:
                                update_allocations(session, run_id, partial_alloc)
                        except Exception as e:
                            print(f"[runner] Erreur allocation progressive: {e}")
                        finally:
                            _write_lock.release()

                    threading.Thread(target=_write, daemon=True).start()

                opt_prog.start(run_id=run_id, message="Préparation de l'optimisation…")
                opt_prog.set_phase(
                    "optimisation",
                    f"Optimisation Differential Evolution ({len(t_opt)} titres)…",
                )
                try:
                    weights, metric = optimize_portfolio_de(
                        t_opt, rets, mat_access, active_b,
                        progress_cb=opt_prog.update_de, on_new_best=_on_new_best,
                        should_stop=lambda: opt_prog.snapshot()["stop_requested"],
                    )
                finally:
                    opt_prog.finish(message="Optimisation terminée.")
```

`threading` est déjà importé en haut de `runner.py` (ligne 25) — aucun nouvel import nécessaire.

- [ ] **Step 2: Write a test for the async write + skip-if-busy behavior**

```python
# backend/tests/test_finance/test_buffett_progressive_allocation.py — ajouter à la fin du fichier

def test_on_new_best_async_write_does_not_block(monkeypatch):
    """Reproduit le pattern _on_new_best de runner.py : l'appel doit revenir
    immediatement meme si l'ecriture DB sous-jacente est lente, et une 2e
    ecriture pendant que la 1ere tourne encore doit etre ignoree sans erreur
    (pas d'empilement de threads)."""
    import threading
    import time

    write_started = threading.Event()
    write_can_finish = threading.Event()
    write_count = {"n": 0}

    def slow_write() -> None:
        write_count["n"] += 1
        write_started.set()
        write_can_finish.wait(timeout=2)

    _write_lock = threading.Lock()

    def on_new_best(_w_matrix) -> None:
        if not _write_lock.acquire(blocking=False):
            return

        def _write() -> None:
            try:
                slow_write()
            finally:
                _write_lock.release()

        threading.Thread(target=_write, daemon=True).start()

    t0 = time.monotonic()
    on_new_best(object())          # 1ere ecriture : demarre un thread, revient tout de suite
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5           # n'a PAS attendu la fin de l'ecriture (qui bloque sur l'Event)

    assert write_started.wait(timeout=1)
    on_new_best(object())          # 2e ecriture pendant que la 1ere tourne encore -> ignoree
    write_can_finish.set()
    time.sleep(0.2)                # laisse le thread de la 1ere ecriture se terminer
    assert write_count["n"] == 1   # la 2e a bien ete ignoree, pas d'empilement
```

- [ ] **Step 3: Run the test**

Run: `cd backend && uv run pytest tests/test_finance/test_buffett_progressive_allocation.py -v`
Expected: PASS

- [ ] **Step 4: Run the fuller verification slice**

Run: `cd backend && uv run pytest tests/test_finance/ -q`
Expected: PASS (aucune régression sur le reste de la suite)

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/finance/buffett/runner.py tests/test_finance/test_buffett_progressive_allocation.py
git commit -m "$(cat <<'EOF'
perf(buffett): ecriture progressive async + should_stop sur le run auto

_on_new_best part desormais dans un thread daemon (verrou non
bloquant, ecriture ignoree si une precedente tourne encore) au lieu de
bloquer la boucle DE. Cable should_stop sur optimization_progress pour
le bouton d'arret manuel (feature suivante).
EOF
)"
```

---

### Task 5 : `buffett.py` — `should_stop` sur le bouton manuel + endpoint stop

**Files:**
- Modify: `backend/app/api/finance/buffett.py`

**Interfaces:**
- Produces: `POST /finance/buffett/optimization/stop` → `{"message": "Arrêt demandé."}`. Utilisé par Task 6 (frontend), pour les deux points d'entrée DE (un seul flag partagé, un seul DE actif à la fois).

- [ ] **Step 1: Câbler `should_stop` sur le bouton manuel**

Dans `backend/app/api/finance/buffett.py`, l'appel actuel (autour de la ligne 525-527) :

```python
            mat_access, active_b = prepare_optimization(t_opt, df_m)
            opt_prog.set_phase("optimisation", f"Optimisation Differential Evolution ({len(t_opt)} titres)…")
            weights, sharpe = optimize_portfolio_de(
                t_opt, rets, mat_access, active_b, progress_cb=opt_prog.update_de,
            )
```

devient :

```python
            mat_access, active_b = prepare_optimization(t_opt, df_m)
            opt_prog.set_phase("optimisation", f"Optimisation Differential Evolution ({len(t_opt)} titres)…")
            weights, sharpe = optimize_portfolio_de(
                t_opt, rets, mat_access, active_b, progress_cb=opt_prog.update_de,
                should_stop=lambda: opt_prog.snapshot()["stop_requested"],
            )
```

- [ ] **Step 2: Nouvel endpoint d'arrêt**

Dans `backend/app/api/finance/buffett.py`, juste après `portfolio_progress` (ligne ~101), ajouter :

```python
@router.post("/buffett/optimization/stop")
def optimization_stop():
    """Demande l'arrêt de l'optimisation DE en cours (run automatique OU bouton
    manuel « Créer le portefeuille optimal » -- un seul DE actif à la fois,
    cf. is_analysis_running()). Pris en compte à la fin du seed en cours, jamais
    au milieu -- pas d'arrêt instantané, mais jamais de seed interrompu compté
    dans les stats de robustesse."""
    from app.services.finance.buffett import optimization_progress as opt_prog
    opt_prog.request_stop()
    return {"message": "Arrêt demandé — pris en compte à la fin du seed en cours."}
```

- [ ] **Step 3: Write a test for the new endpoint**

Utiliser la fixture `client` déjà définie en haut de `backend/tests/test_finance/test_api.py`
(ligne 23, `create_app()` + DB SQLite en mémoire) — même pattern que
`test_portfolio_create_409_when_analysis_already_running` juste au-dessus dans ce même fichier :

```python
# backend/tests/test_finance/test_api.py — ajouter à la fin du fichier

def test_optimization_stop_sets_flag(client):
    from app.services.finance.buffett import optimization_progress as opt_prog

    opt_prog.reset()
    try:
        res = client.post("/finance/buffett/optimization/stop")
        assert res.status_code == 200
        assert opt_prog.snapshot()["stop_requested"] is True
    finally:
        opt_prog.reset()
```

- [ ] **Step 4: Run test**

Run: `cd backend && uv run pytest tests/test_finance/test_api.py -k optimization_stop -v`
Expected: PASS

- [ ] **Step 5: Run the fuller verification slice**

Run: `cd backend && uv run pytest tests/test_finance/ -q`
Expected: PASS (aucune régression)

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/api/finance/buffett.py tests/test_finance/test_api.py
git commit -m "$(cat <<'EOF'
feat(buffett): endpoint d'arret manuel de l'optimisation DE

POST /finance/buffett/optimization/stop -- positionne le flag partage
consomme par should_stop cote optimizer. Fonctionne pour le run
automatique ET le bouton manuel (un seul DE actif a la fois). Cable
should_stop sur le bouton manuel (deja fait sur le run auto, task
precedente).
EOF
)"
```

---

### Task 6 : Frontend — compteur de seed + bouton Arrêter

**Files:**
- Modify: `frontend/lib/finance.ts`
- Modify: `frontend/components/finance/buffett-ui.tsx`
- Modify: `frontend/components/finance/BuffettActionsPanel.tsx`
- Modify: `frontend/components/finance/BuffettTab.tsx`

**Interfaces:**
- Produces: `financeApi.optimizationStop(): Promise<{ message: string }>`. `DeProgressBar` accepte une nouvelle prop optionnelle `onStop?: () => void`.

- [ ] **Step 1: `financeApi.optimizationStop` + `seed_num` dans le type**

Dans `frontend/lib/finance.ts`, le bloc actuel (lignes ~448-458) :

```tsx
  /** Progression de l'optimisation DE (barre de chargement du bouton 3) */
  portfolioProgress: () =>
    get<{
      active: boolean;
      phase: "idle" | "preparation" | "optimisation" | "finalisation";
      iteration: number;
      convergence: number;
      progress_pct: number;
      message: string;
      run_id: number | null;
    }>("/portfolio/progress"),
```

devient :

```tsx
  /** Progression de l'optimisation DE (barre de chargement du bouton 3) */
  portfolioProgress: () =>
    get<{
      active: boolean;
      phase: "idle" | "preparation" | "optimisation" | "finalisation";
      seed_num: number;
      iteration: number;
      convergence: number;
      progress_pct: number;
      message: string;
      run_id: number | null;
    }>("/portfolio/progress"),
  /** Arrête l'optimisation DE en cours (run auto ou bouton manuel) */
  optimizationStop: () =>
    post<{ message: string }>("/buffett/optimization/stop"),
```

- [ ] **Step 2: `DeProgressBar` — compteur de seed + bouton Arrêter**

Dans `frontend/components/finance/buffett-ui.tsx`, l'import actuel (ligne 5) :

```tsx
import { financeApi } from "@/lib/finance";
```

devient :

```tsx
import { useEffect, useState } from "react";
import { financeApi } from "@/lib/finance";
```

Le composant `DeProgressBar` actuel (lignes ~49-83) :

```tsx
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

devient :

```tsx
export function DeProgressBar({
  optProgress, onStop,
}: {
  optProgress: OptProgress | null;
  onStop?: () => void;
}) {
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    if (!optProgress?.active) setStopping(false);
  }, [optProgress?.active]);

  if (!optProgress) return null;

  const handleStop = () => {
    if (!onStop || stopping) return;
    setStopping(true);
    onStop();
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--muted-foreground)]">
          {optProgress.active
            ? (PHASE_LABEL[optProgress.phase] || "En cours…")
            : (optProgress.message || "Terminé")}
          {optProgress.active && optProgress.phase === "optimisation"
            ? ` · seed ${optProgress.seed_num || 1}${
                optProgress.iteration > 0 ? ` · génération ${optProgress.iteration}` : ""
              }`
            : ""}
        </span>
        <div className="flex items-center gap-2">
          {optProgress.active && optProgress.phase === "optimisation" && onStop && (
            <button
              type="button"
              onClick={handleStop}
              disabled={stopping}
              className="text-[var(--destructive)] hover:underline disabled:opacity-50 disabled:no-underline"
            >
              {stopping ? "Arrêt demandé…" : "⏹ Arrêter"}
            </button>
          )}
          {optProgress.active && optProgress.phase === "optimisation" && (
            <span className="font-mono text-[var(--muted-foreground)]">
              {fmt(optProgress.progress_pct, 0)}%
            </span>
          )}
        </div>
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

- [ ] **Step 3: `BuffettActionsPanel.tsx` — état synthétique initial + `onStop`**

`seed_num` devient un champ non-optionnel de `OptProgress` (dérivé de `financeApi.portfolioProgress()`,
Step 1). L'état synthétique posé par `createPortfolio()` avant le premier vrai poll doit donc
l'inclure, sinon `tsc` échoue (propriété manquante). Dans
`frontend/components/finance/BuffettActionsPanel.tsx`, la ligne actuelle (dans `createPortfolio`) :

```tsx
      setOptProgress({ active: true, phase: "preparation", iteration: 0,
        convergence: 0, progress_pct: 0, message: "Démarrage…", run_id: null });
```

devient :

```tsx
      setOptProgress({ active: true, phase: "preparation", seed_num: 0, iteration: 0,
        convergence: 0, progress_pct: 0, message: "Démarrage…", run_id: null });
```

Puis, ajouter juste avant le `return` du composant (après `createPortfolio`, avant la ligne
`return (`) :

```tsx
  const stopOptimization = async () => {
    try {
      await financeApi.optimizationStop();
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Erreur arrêt optimisation");
    }
  };
```

Puis la ligne actuelle :

```tsx
      <DeProgressBar optProgress={optProgress} />
```

devient :

```tsx
      <DeProgressBar optProgress={optProgress} onStop={stopOptimization} />
```

- [ ] **Step 4: `BuffettTab.tsx` — passer `onStop`**

Dans `frontend/components/finance/BuffettTab.tsx`, ajouter juste avant `const openRun = async (id: number) => {` (ligne ~102) :

```tsx
  const stopOptimization = async () => {
    try {
      await financeApi.optimizationStop();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur arrêt optimisation");
    }
  };
```

Puis la ligne actuelle (ligne ~189) :

```tsx
          <DeProgressBar optProgress={optProgress} />
```

devient :

```tsx
          <DeProgressBar optProgress={optProgress} onStop={stopOptimization} />
```

- [ ] **Step 5: Vérifier types + lint**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

Run: `cd frontend && npx eslint components/finance/buffett-ui.tsx components/finance/BuffettActionsPanel.tsx components/finance/BuffettTab.tsx lib/finance.ts`
Expected: pas de nouvelle erreur au-delà de la baseline déjà connue (pré-existante, hors scope —
cf. Task 4 du plan précédent, `orchestration/finis/` ou `a-faire/2026-07-07-buffett-optimisation-
progressive-plan.md`, qui documente déjà cette baseline).

- [ ] **Step 6: Commit**

```bash
cd frontend
git add lib/finance.ts components/finance/buffett-ui.tsx components/finance/BuffettActionsPanel.tsx components/finance/BuffettTab.tsx
git commit -m "$(cat <<'EOF'
feat(buffett): bouton Arreter + compteur de seed sur la barre DE

DeProgressBar affiche desormais "seed N . generation M" et un bouton
Arreter (toujours actif des le debut) qui appelle le nouvel endpoint
POST /buffett/optimization/stop. Cable sur les deux points d'entree
(run automatique et bouton manuel), un seul DE actif a la fois donc un
seul bouton suffit.
EOF
)"
```

---

### Task 7 : Vérification end-to-end manuelle

**Files:** aucun (validation, pas de code).

- [ ] **Step 1: Lancer un run réduit** (même procédé que la Task 5 du plan précédent : petite
liste de tickers via `csv_path`, backend + frontend de vérification sur des ports séparés pour ne
pas toucher une session existante de l'utilisateur).

- [ ] **Step 2: Observer le compteur de seed**

Vérifier que la barre affiche « seed 1 · génération N », puis après convergence du 1er seed,
bascule sur « seed 2 · génération 1 » (génération repart bien à 1, pas de cumul global).

- [ ] **Step 3: Cliquer Arrêter**

Vérifier : le bouton passe en « Arrêt demandé… » (désactivé), le seed en cours continue jusqu'à sa
fin naturelle ou son plafond, PUIS le run passe à `statut: "termine"`. L'allocation finale doit
être cohérente (pas de résultat partiel/incomplet).

- [ ] **Step 4: Vérifier la perf**

Sur un run plus long (si possible, sinon différer à un run réel futur), confirmer que le rythme
générations/seconde reste stable dans le temps (pas de ralentissement progressif comme avant le
correctif). Vérifier `data/mission-control.db-wal` reste petit (quelques centaines de Ko) au lieu
de grossir sur plusieurs Mo.
