# Résilience de l'analyse Buffett / optimisation DE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger le bug qui fait qu'une analyse Buffett (scoring + optimisation DE multi-seed) rapportée comme "terminée" peut en réalité avoir été interrompue avant que l'optimisation DE ait produit un portefeuille, sans aucune erreur visible — et faire persister la courbe du meilleur score STARR en direct à travers un refresh de page.

**Architecture:** Deux correctifs backend ciblés (pas de migration DB) : (1) `run_buffett_analysis` ne doit plus avaler silencieusement une exception survenue pendant la phase d'optimisation DE ; (2) l'endpoint `/buffett/progress` ne doit plus reclasser un run "en_cours" en "termine" simplement parce que le scoring des tickers est à 100 % — seul `finalize_run()` (appelé après la pipeline COMPLETE, scoring + DE + persistance de l'allocation) a le droit de marquer "termine". Un correctif frontend fait persister l'historique du graphique `DeStarrChart` (déjà écrit, non testé bout-en-bout) dans `sessionStorage` pour survivre à un remount/refresh tant que le run est actif côté serveur.

**Tech Stack:** FastAPI, SQLModel/SQLite, pytest ; Next.js/React, Vitest + Testing Library.

## Global Constraints

- Aucune migration Alembic dans ce plan (pas de nouvelle colonne DB) — voir "Hors scope" en bas.
- Ne pas toucher à la logique DE elle-même (`optimizer.py`) : elle boucle déjà correctement sur les seeds jusqu'à `should_stop()` — le bug est dans la gestion d'erreur et le statut du run autour d'elle.
- Respecter le style du dépôt : commentaires uniquement quand le POURQUOI n'est pas évident (bugs passés, contrainte cachée) — pas de commentaire qui répète ce que fait le code.
- Tests backend : `cd backend && uv run pytest -v <fichier>`. Tests frontend : `cd frontend && npx vitest run <fichier>`.

---

### Task 1: Ne plus avaler silencieusement une exception pendant l'optimisation DE

**Contexte du bug :** dans `run_buffett_analysis`, tout le bloc d'optimisation (budgets, dedup, téléchargement des cours, `optimize_portfolio_de`, discrétisation, écriture de l'allocation) est enveloppé dans un seul `try/except Exception as e: print(...)`. Si une exception survient n'importe où là-dedans, elle est juste imprimée dans la console et la fonction retourne quand même un dict "de succès" (sans clé `error`). `job_monthly_buffett` (scheduler_stub.py) fait `erreur = result.get("error") or result.get("erreur")` puis marque le run `"termine"` si `erreur` est falsy — donc un plantage pendant le DE est actuellement rapporté comme un run terminé avec succès, sans portefeuille et sans aucune erreur visible.

**Files:**
- Modify: `backend/app/services/finance/buffett/runner.py:485-667` (fonction `run_buffett_analysis`)
- Test: `backend/tests/test_finance/test_buffett_optimization_error_surfacing.py` (nouveau)

**Interfaces:**
- Consumes : `run_buffett_analysis(session_factory, csv_path, max_workers=10, n_sim=500_000, on_progress=None, run_id=None) -> dict` (signature inchangée).
- Produces : le dict retourné contient désormais toujours une clé `"error": str | None`. `job_monthly_buffett` (scheduler_stub.py:149, déjà écrit — `erreur = result.get("error") or result.get("erreur")`) consomme cette clé sans modification nécessaire de son côté.

- [ ] **Step 1: Write the failing test**

**Attention isolation :** `run_buffett_analysis` lit/écrit par défaut de VRAIS chemins partagés avec le serveur dev réel (`backend/data/cache_status.json`, `ToutBroker.xlsx` via plusieurs chemins de repli dans `find_broker_file()`, `params.json` utilisateur). `CacheManager()` est construit avec un paramètre par défaut lié **à l'import du module** (`cache_file: str = Config.CACHE_FILE`) — monkeypatcher `Config.CACHE_FILE` seul NE redirige PAS `CacheManager()` appelé sans argument. Le test ci-dessous isole donc explicitement chaque chemin réel pour ne **jamais** toucher aux données réelles de l'utilisateur ni risquer une écriture concurrente avec le serveur dev en cours d'exécution.

```python
"""Une exception pendant la phase d'optimisation DE (bug reseau, erreur de
calcul...) ne doit plus etre avalee silencieusement : avant ce correctif,
`run_buffett_analysis` renvoyait un dict "de succes" (sans cle 'error') meme
si l'optimisation avait plante, et `job_monthly_buffett` marquait alors le
run "termine" sans portefeuille et sans aucune erreur visible (#bug rapporte
: "l'analyse DE s'est arretee seule, sans graphique, sans erreur").

Tous les chemins reels (cache, ToutBroker.xlsx, params.json) sont isoles vers
tmp_path : ce test ne doit JAMAIS lire/ecrire les vraies donnees financieres
de l'utilisateur ni risquer une course avec le serveur dev reellement lance
(meme process CWD == backend/, memes chemins relatifs par defaut)."""

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.finance.buffett import broker_availability, broker_budgets, runner
from app.services.finance.buffett.cache_manager import CacheManager as RealCacheManager
from app.services.finance.buffett.config import Config


def _isolate_buffett_paths(monkeypatch, tmp_path):
    """Redirige tous les chemins reels de Config vers tmp_path, et neutralise
    tout acces reseau/fichier best-effort (bond yields, ToutBroker.xlsx)."""
    monkeypatch.setattr(Config, "CACHE_FILE", str(tmp_path / "cache_status.json"))
    monkeypatch.setattr(Config, "FOLDER_PATH", str(tmp_path / "financials_by_company"))
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "PARAMS_FILE", str(tmp_path / "absent_params.json"))
    # CacheManager() est appele SANS argument dans runner.py -- son parametre
    # par defaut est lie a l'import du module (pas au Config courant), donc le
    # patch Config.CACHE_FILE ci-dessus ne suffit pas a le rediriger : on
    # remplace directement le nom utilise dans le namespace de runner.py.
    monkeypatch.setattr(
        runner, "CacheManager", lambda: RealCacheManager(str(tmp_path / "cache_status.json"))
    )
    # Jamais de vrai ToutBroker.xlsx (find_broker_file() essaie plusieurs
    # chemins de repli, dont des relatifs -- un simple Config.BROKER_FILE ne
    # suffirait pas a l'empecher de trouver le vrai fichier de l'utilisateur).
    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: None)
    monkeypatch.setattr(runner, "_refresh_bond_yields", lambda: None)


def test_run_buffett_analysis_surfaces_optimization_exception(tmp_path, monkeypatch):
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("AAPL;Apple;NASDAQ;Action\n")

    # Le scoring du ticker echoue proprement (pas de reseau dans le test) --
    # on ne teste pas le scoring ici, seulement la phase d'optimisation.
    monkeypatch.setattr(runner, "_internet_available", lambda timeout=4.0: True)
    monkeypatch.setattr(runner, "fetch_data", lambda ticker, rl: None)

    def _boom():
        raise RuntimeError("boom - simulated DE crash")

    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", _boom)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(engine),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )

    assert result.get("error") is not None
    assert "boom" in result["error"]


def test_run_buffett_analysis_error_is_none_on_success(tmp_path, monkeypatch):
    """Non-regression : un run sans ticker eligible (aucune optimisation a
    tenter) reste un succes normal (`error` a None), pas un echec."""
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("")  # aucun ticker

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(create_engine("sqlite://")),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )
    # Chemin "aucun ticker dans tickers.csv" : dict d'erreur explicite existant,
    # pas de cle "error" a valider ici (cf. runner.py:364-365) -- ce test verifie
    # juste qu'il ne plante pas et reste explicite.
    assert result.get("error") == "Aucun ticker dans tickers.csv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_finance/test_buffett_optimization_error_surfacing.py -v`
Expected: `test_run_buffett_analysis_surfaces_optimization_exception` FAILS on `assert result.get("error") is not None` (actuellement `None`, l'exception est avalée).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/services/finance/buffett/runner.py`, locate (around line 486):

```python
    # Optimisation DE
    from . import optimization_progress as opt_prog
    try:
```

Add an `opt_error` variable right before the `try:`:

```python
    # Optimisation DE
    from . import optimization_progress as opt_prog
    opt_error: str | None = None
    try:
```

Then locate the matching `except` block (around line 659):

```python
    except Exception as e:
        print(f"[runner] Erreur optimisation: {e}")
        opt_prog.finish(message=f"Erreur optimisation : {e}")

    return {
        "n_analyzed": len(results),
        "duree_sec": round(time.time() - start_t, 1),
        "n_deleted": len(deleted_tickers),
    }
```

Replace with:

```python
    except Exception as e:
        print(f"[runner] Erreur optimisation: {e}")
        opt_prog.finish(message=f"Erreur optimisation : {e}")
        opt_error = str(e)

    return {
        "n_analyzed": len(results),
        "duree_sec": round(time.time() - start_t, 1),
        "n_deleted": len(deleted_tickers),
        "error": opt_error,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_finance/test_buffett_optimization_error_surfacing.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run the full Buffett test suite to check for regressions**

Run: `cd backend && uv run pytest tests/test_finance/ -v -k buffett`
Expected: all PASS (no existing test asserts the old shape of the final return dict).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/finance/buffett/runner.py backend/tests/test_finance/test_buffett_optimization_error_surfacing.py
git commit -m "fix(buffett): surfacer les exceptions de l'optimisation DE au lieu de les avaler"
```

---

### Task 2: Ne plus marquer un run "termine" tant que l'optimisation DE n'a pas reellement fini

**Contexte du bug :** dans `GET /buffett/progress` (`backend/app/api/finance/buffett.py:43-87`), quand aucune analyse ne tourne réellement dans ce process (`is_analysis_running()` → `False`), le code cherche les runs restés `"en_cours"` ou `"interrompu"` et, si le scoring des tickers est à 100 % (`n_tickers_analyzed >= n_tickers_total`), les marque `"termine"` — **y compris un run déjà correctement marqué `"interrompu"`**, puisque la condition n'est pas restreinte à `statut == "en_cours"`. Le scoring des tickers n'est qu'une PARTIE de la pipeline : l'optimisation DE (seeds illimités, peut durer des heures) vient après et peut avoir été interrompue (crash, redémarrage `--reload`) sans jamais avoir produit de portefeuille. `statut` ne devrait passer à `"termine"` que via `finalize_run()`, appelé uniquement après la pipeline complète. Ce correctif explique directement le symptôme rapporté : une analyse dont le DE est tué en vol se voit reclassée "terminée" au prochain poll de l'UI (toutes les 5s), sans erreur ni graphique.

**Files:**
- Modify: `backend/app/api/finance/buffett.py:43-87` (fonction `buffett_progress`)
- Test: `backend/tests/test_finance/test_buffett_progress_stuck_run.py` (nouveau)

**Interfaces:**
- Consumes : `BuffettRun.statut`, `BuffettRun.n_tickers_total`, `BuffettRun.n_tickers_analyzed` (modèle existant, inchangé).
- Produces : `GET /finance/buffett/progress` ne renvoie plus jamais `statut: "termine"` pour un run que `finalize_run()` n'a pas explicitement terminé.

- [ ] **Step 1: Write the failing test**

```python
"""GET /buffett/progress ne doit jamais reclasser un run "en_cours" en
"termine" seulement parce que le scoring des tickers est a 100% -- seul
finalize_run() (appele apres la PIPELINE COMPLETE, scoring + optimisation DE
+ persistance de l'allocation) a le droit de marquer "termine". Avant ce
correctif, un run dont le DE etait tue en vol (crash, redemarrage --reload)
etait reclasse "termine" au prochain poll, sans portefeuille et sans erreur
visible (#bug rapporte : "l'analyse DE s'est arretee seule")."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app
from app.models.finance import BuffettRun


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        c.engine = engine  # type: ignore[attr-defined]
        yield c


def test_dead_run_with_scoring_done_is_marked_interrompu_not_termine(client):
    with Session(client.engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="en_cours",
                          n_tickers_total=100, n_tickers_analyzed=100)
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id

    r = client.get("/finance/buffett/progress")
    assert r.status_code == 200
    assert r.json()["statut"] == "interrompu"

    with Session(client.engine) as s:
        refreshed = s.get(BuffettRun, run_id)
        assert refreshed.statut == "interrompu"
        assert refreshed.erreur == "Process interrompu (relancez pour reprendre)"


def test_already_interrompu_run_is_left_untouched(client):
    with Session(client.engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="interrompu",
                          n_tickers_total=100, n_tickers_analyzed=100,
                          erreur="Process interrompu (relancez pour reprendre)")
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id

    r = client.get("/finance/buffett/progress")
    assert r.status_code == 200
    assert r.json()["statut"] == "interrompu"

    with Session(client.engine) as s:
        refreshed = s.get(BuffettRun, run_id)
        assert refreshed.statut == "interrompu"  # jamais reclasse "termine"


def test_partially_scored_run_still_marked_interrompu(client):
    """Non-regression du comportement existant : un run interrompu AVANT la
    fin du scoring (n_analyzed < n_total) reste 'interrompu'."""
    with Session(client.engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="en_cours",
                          n_tickers_total=100, n_tickers_analyzed=42)
        s.add(run)
        s.commit()

    r = client.get("/finance/buffett/progress")
    assert r.json()["statut"] == "interrompu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_finance/test_buffett_progress_stuck_run.py -v`
Expected: `test_already_interrompu_run_is_left_untouched` FAILS — l'ancien code reclasse le run en `"termine"` car `n_tickers_analyzed >= n_tickers_total` est vrai, peu importe le statut de départ.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/finance/buffett.py`, replace (around line 43-72):

```python
    # Si aucune analyse ne tourne reellement dans ce process, un run encore
    # "en_cours" en base est en fait interrompu (programme ferme) -> on le marque
    # immediatement resumable pour debloquer le bouton "Reprendre".
    if not active:
        stuck = session.exec(
            select(BuffettRun).where(
                BuffettRun.statut.in_(["en_cours", "interrompu"])  # type: ignore[attr-defined]
            )
        ).all()
        changed = False
        for sr in stuck:
            # Analyse complète (100 %) mais process fermé avant le marquage final :
            # on la termine au lieu de boucler indéfiniment sur "Reprendre".
            if (sr.n_tickers_total or 0) > 0 and (sr.n_tickers_analyzed or 0) >= sr.n_tickers_total:
                sr.statut = "termine"
                sr.erreur = None
                session.add(sr)
                changed = True
            elif sr.statut == "en_cours":
                sr.statut = "interrompu"
                sr.erreur = "Process interrompu (relancez pour reprendre)"
                session.add(sr)
                changed = True
        if changed:
            session.commit()
```

with:

```python
    # Si aucune analyse ne tourne reellement dans ce process, un run encore
    # "en_cours" en base est en fait interrompu (programme ferme) -> on le marque
    # immediatement resumable pour debloquer le bouton "Reprendre". Le scoring
    # des tickers a 100% NE VEUT PAS DIRE que la pipeline est terminee : l'
    # optimisation DE (seeds illimites, peut durer des heures) vient juste
    # apres et peut avoir ete tuee en vol (crash, redemarrage --reload) sans
    # avoir produit de portefeuille. Seul finalize_run() (appele apres la
    # pipeline COMPLETE) a le droit de marquer "termine" -- ne jamais le faire
    # ici, sous peine de masquer un DE jamais termine sans aucune erreur
    # visible (et de reclasser a tort un run deja "interrompu").
    if not active:
        stuck = session.exec(
            select(BuffettRun).where(BuffettRun.statut == "en_cours")  # type: ignore[attr-defined]
        ).all()
        changed = False
        for sr in stuck:
            sr.statut = "interrompu"
            sr.erreur = "Process interrompu (relancez pour reprendre)"
            session.add(sr)
            changed = True
        if changed:
            session.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_finance/test_buffett_progress_stuck_run.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Run the full backend test suite to check for regressions**

Run: `cd backend && uv run pytest -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/finance/buffett.py backend/tests/test_finance/test_buffett_progress_stuck_run.py
git commit -m "fix(buffett): ne plus reclasser un run interrompu en 'termine' sur le seul scoring 100%"
```

---

### Task 3: Faire survivre l'historique du graphique DE (best-score) à un refresh de page

**Contexte :** `frontend/components/finance/DeStarrChart.tsx` (déjà écrit, non committé, jamais testé) accumule l'historique du meilleur score STARR en `useState` local. Un refresh de page ou un remount du composant (navigation entre onglets) reset cet historique à vide alors que le DE tourne peut-être encore depuis des heures côté serveur — l'utilisateur perd la courbe déjà accumulée (même si la valeur "meilleur score actuel" réapparaît correctement au prochain poll, il faut à nouveau 2 points avant que le graphique ne réapparaisse). On fait persister l'historique dans `sessionStorage`, keyed par `run_id`, pour le récupérer au remount tant que c'est le même run.

**Files:**
- Modify: `frontend/components/finance/DeStarrChart.tsx` (fichier déjà présent, non commité)
- Test: `frontend/__tests__/components/de-starr-chart.test.tsx` (nouveau)

**Interfaces:**
- Consumes : `OptProgress` (type existant, `frontend/components/finance/buffett-ui.tsx:41`) — `{ active, run_id, best_score, ... }`.
- Produces : `DeStarrChart({ optProgress }: { optProgress: OptProgress | null })` — signature inchangée, comportement enrichi (persistance `sessionStorage`).

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { DeStarrChart } from '@/components/finance/DeStarrChart'
import type { OptProgress } from '@/components/finance/buffett-ui'

function progress(overrides: Partial<OptProgress>): OptProgress {
  return {
    active: true, phase: 'optimisation', seed_num: 1, iteration: 1,
    convergence: 0.1, progress_pct: 10, message: '', run_id: 1,
    stop_requested: false, best_score: null,
    ...overrides,
  }
}

describe('DeStarrChart', () => {
  beforeEach(() => {
    sessionStorage.clear()
    cleanup()
  })

  it("n'affiche rien tant qu'il n'y a pas 2 points", () => {
    const { rerender } = render(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    rerender(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('affiche le graphique après 2 valeurs distinctes du même run', () => {
    const { rerender } = render(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    rerender(<DeStarrChart optProgress={progress({ best_score: 0.8 })} />)
    expect(screen.getByRole('img')).toBeInTheDocument()
    expect(screen.getByText('min 0,5000')).toBeInTheDocument()
    expect(screen.getByText('max 0,8000')).toBeInTheDocument()
  })

  it('reprend l\'historique déjà accumulé après un remount (refresh de page simulé)', () => {
    const { rerender, unmount } = render(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    rerender(<DeStarrChart optProgress={progress({ best_score: 0.8 })} />)
    expect(screen.getByText('max 0,8000')).toBeInTheDocument()

    unmount()
    // Remount "à froid" du même composant, comme après un refresh de page --
    // l'historique doit être repris depuis sessionStorage (même run_id), pas
    // reparti à un seul point.
    render(<DeStarrChart optProgress={progress({ best_score: 0.8 })} />)
    expect(screen.getByText('max 0,8000')).toBeInTheDocument()
    expect(screen.getByText('min 0,5000')).toBeInTheDocument()
  })

  it("ne réutilise pas l'historique d'un run_id différent", () => {
    const { rerender, unmount } = render(<DeStarrChart optProgress={progress({ run_id: 1, best_score: 0.5 })} />)
    rerender(<DeStarrChart optProgress={progress({ run_id: 1, best_score: 0.8 })} />)
    unmount()

    const { rerender: rerender2 } = render(<DeStarrChart optProgress={progress({ run_id: 2, best_score: 0.1 })} />)
    rerender2(<DeStarrChart optProgress={progress({ run_id: 2, best_score: 0.2 })} />)
    expect(screen.getByText('min 0,1000')).toBeInTheDocument()
    expect(screen.getByText('max 0,2000')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run __tests__/components/de-starr-chart.test.tsx`
Expected: le test "reprend l'historique déjà accumulé après un remount" FAILS — sans persistance, le remount repart avec `history = [0.8]` (1 seul point, rien ne s'affiche).

- [ ] **Step 3: Write minimal implementation**

Replace the full content of `frontend/components/finance/DeStarrChart.tsx` with:

```tsx
"use client";

/** Évolution EN DIRECT du meilleur score d'optimisation (STARR pénalisé)
 *  trouvé par le Differential Evolution, pendant qu'il tourne -- pas
 *  seulement affiché une fois terminé. Pas d'historique côté serveur : on
 *  accumule les valeurs polled via `optProgress` (déjà rafraîchi toutes les
 *  3s par le parent), persisté en sessionStorage par run_id pour survivre à
 *  un refresh de page / remount tant que le DE tourne toujours côté serveur. */

import { useEffect, useRef, useState } from "react";
import type { OptProgress } from "./buffett-ui";

const STORAGE_PREFIX = "buffett-de-history-";

function loadHistory(runId: number): number[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + runId);
    return raw ? (JSON.parse(raw) as number[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(runId: number, history: number[]): void {
  try {
    sessionStorage.setItem(STORAGE_PREFIX + runId, JSON.stringify(history));
  } catch {
    // sessionStorage indisponible (navigation privée, quota) -- best-effort.
  }
}

export function DeStarrChart({ optProgress }: { optProgress: OptProgress | null }) {
  const [history, setHistory] = useState<number[]>([]);
  const lastRunRef = useRef<number | null>(null);

  useEffect(() => {
    if (!optProgress?.active || optProgress.best_score == null || optProgress.run_id == null) return;
    const runId = optProgress.run_id;
    const score = optProgress.best_score;
    if (lastRunRef.current !== runId) {
      lastRunRef.current = runId;
      const restored = loadHistory(runId);
      const next = restored.length && restored[restored.length - 1] === score
        ? restored
        : [...restored, score];
      setHistory(next);
      saveHistory(runId, next);
      return;
    }
    setHistory((h) => {
      if (h[h.length - 1] === score) return h;
      const next = [...h, score];
      saveHistory(runId, next);
      return next;
    });
  }, [optProgress?.best_score, optProgress?.active, optProgress?.run_id]);

  if (history.length < 2) return null;

  const W = 100, H = 28;
  const min = Math.min(...history);
  const max = Math.max(...history);
  const span = max - min || 1;
  const coords = history
    .map((v, i) => `${((i / (history.length - 1)) * W).toFixed(2)},${(H - ((v - min) / span) * H).toFixed(2)}`)
    .join(" ");

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">
          Meilleur score d&apos;optimisation (STARR pénalisé) — en direct
        </p>
        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
          {history[history.length - 1].toFixed(4)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-20 w-full"
           role="img" aria-label="Évolution du meilleur score d'optimisation en direct">
        <polyline points={coords} fill="none" stroke="var(--success)" strokeWidth={0.6}
                  vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>min {min.toFixed(4)}</span>
        <span>max {max.toFixed(4)}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run __tests__/components/de-starr-chart.test.tsx`
Expected: all 4 tests PASS.

- [ ] **Step 5: Typecheck and lint**

Run: `cd frontend && npx tsc --noEmit && npx eslint components/finance/DeStarrChart.tsx`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/finance/DeStarrChart.tsx frontend/__tests__/components/de-starr-chart.test.tsx frontend/components/finance/BuffettTab.tsx frontend/components/finance/BuffettActionsPanel.tsx frontend/components/finance/buffett-ui.tsx
git commit -m "feat(buffett): persister l'historique du graphique DE en sessionStorage (survit à un refresh)"
```

---

## Hors scope (délibérément non traité par ce plan)

- **Détacher l'analyse Buffett du process uvicorn `--reload`** (ex. worker séparé, IPC via DB) : réglerait la cause *déclenchante* la plus probable des redémarrages en cours de run (tout fichier `.py` modifié pendant une analyse tue le thread), mais c'est une réécriture d'architecture (process séparé, verrou cross-process, supervision) disproportionnée par rapport au bug réellement rapporté. Les Tasks 1-2 de ce plan garantissent qu'un tel redémarrage laisse désormais le run dans un état correct (`"interrompu"`, resumable) au lieu de le faire passer inaperçu pour "terminé".
- **Persistance DB de `seed_num`/`iteration`/`convergence`/`best_score`** : apporterait peu au-delà de ce que Task 3 couvre déjà (persistance du graphique côté navigateur), pour le coût d'une migration Alembic + logique de synchronisation cross-process. À reconsidérer seulement si un besoin concret d'observabilité multi-appareil apparaît.
- Pratique recommandée en attendant : éviter d'éditer des fichiers `.py` du backend pendant qu'une analyse Buffett longue tourne en dev (`--reload` la tuerait) ; relancer `POST /buffett/run` après un crash reprend automatiquement (tickers déjà scorés sautés, DE relancé).
