# Buffett DE : correctifs de perf + seeds infinis avec arrêt manuel

Statut : à faire · Créé le 2026-07-08

## Contexte

Suite de `orchestration/a-faire/2026-07-07-buffett-optimisation-progressive-design.md` (progression
live de l'optimisation DE, livrée). Deux problèmes/idées identifiés en observant un run réel :

1. **Ralentissement mesuré** : ~0,4s/génération en début de run, ~2,9s/génération après plusieurs
   heures. Cause probable : `_on_new_best` écrit en base **de façon synchrone, dans la boucle
   chaude du DE**, à chaque nouveau meilleur (throttlé 2s). Sur un run de plusieurs heures, le
   journal WAL SQLite grossit sans être checkpointé assez souvent (mesuré : 815 pages/~3,2 Mo en
   attente) — un WAL qui grossit dégrade progressivement les lectures/écritures SQLite, ce qui
   ralentit directement chaque écriture synchrone dans la boucle DE.
2. **Budget de seeds fixe** : `STARR_DE_N_SEEDS = 10` est un compromis arbitraire entre robustesse
   (vérifier que plusieurs départs aléatoires convergent vers un optimum similaire) et durée totale
   (~24 min minimum). Vu que le portefeuille affiché est déjà "le meilleur trouvé jusqu'ici" en
   continu (feature précédente), il est plus cohérent de laisser tourner indéfiniment et de
   laisser l'utilisateur décider quand s'arrêter — un algorithme "anytime" classique.

## Objectif

1. Le WAL SQLite ne grossit plus sur un run long (checkpoint automatique).
2. L'écriture progressive de l'allocation ne bloque plus la boucle DE (asynchrone).
3. Les deux points d'entrée DE (run automatique + bouton manuel "Créer le portefeuille optimal")
   tournent en seeds illimités, avec un bouton « Arrêter » qui termine proprement à la fin du seed
   en cours (jamais au milieu — un seed interrompu ne doit jamais compter dans les stats de
   robustesse inter-seeds).
4. Le plafond de générations par seed (garde-fou anti-boucle-infinie, jamais atteint en pratique
   aujourd'hui à 2000) est relevé à 50 000 pour rester purement défensif.

## Architecture

### 1. Checkpoint WAL automatique

`backend/app/core/db.py` : sur l'engine SQLite, exécuter `PRAGMA wal_autocheckpoint = 200` (au lieu
du défaut ~1000 pages) à la connexion — via l'event listener `_sqlite_pragmas` déjà présent (qui
pose déjà d'autres PRAGMA à la connexion, cf. le fichier existant).

### 2. Écriture progressive asynchrone

Dans `runner.py::_on_new_best` et `buffett.py::_run_portfolio_creation`'s équivalent : au lieu
d'appeler `discretize_allocation` + `update_allocations` directement, on les lance dans un
`threading.Thread(daemon=True)`. Un verrou non bloquant (`threading.Lock().acquire(blocking=False)`)
protège contre l'empilement : si une écriture précédente est encore en cours quand un nouveau
meilleur arrive, on **ignore** cette mise à jour (la suivante, quand elle arrivera, écrira de toute
façon un état plus récent — pas de perte fonctionnelle, juste une mise à jour progressive parmi
d'autres qui saute).

### 3. Seeds infinis + arrêt manuel

**`optimizer.py::optimize_portfolio_de`** :
- Nouveau paramètre `should_stop: Callable[[], bool] | None = None`.
- La boucle `for k in range(n_seeds):` devient `while True:` avec `k` qui s'incrémente à chaque
  itération (`rng=seed + k` reste donc toujours différent, jamais de répétition — déjà garanti par
  construction).
- Après qu'un seed se termine (convergence naturelle ou plafond de générations), vérifier
  `should_stop()` : si vrai, sortir de la boucle `while True`. Jamais vérifié au milieu d'un seed —
  l'arrêt se fait toujours à une frontière de seed.
- Le paramètre `n_seeds` (dérivé de `Config.STARR_DE_N_SEEDS`) est retiré de la fonction — plus
  aucun code ne le lit. `Config.STARR_DE_N_SEEDS` est supprimé de `config.py` (et de tout endroit
  qui le référence encore, ex. tests).

**Nouveau module `optimization_progress.py`** :
- Nouvel état `n_seeds_done: int` (incrémenté à chaque seed terminé), exposé par
  `/finance/portfolio/progress`.
- Nouveau flag `stop_requested: bool`, une fonction `request_stop()` qui le met à `True`, et
  `reset()`/`start()` le remettent à `False`.

**Nouveau endpoint** `POST /finance/buffett/optimization/stop` (dans `buffett.py`) : appelle
`optimization_progress.request_stop()`. Un seul point d'arrêt pour les deux chemins (run
automatique et bouton manuel), cohérent avec la garde `is_analysis_running()` déjà en place (un
seul DE actif à la fois).

**Câblage** : `runner.py` et `buffett.py` passent
`should_stop=lambda: optimization_progress.snapshot()["stop_requested"]` à `optimize_portfolio_de`.

**Frontend** :
- `financeApi.optimizationStop()` → `POST /finance/buffett/optimization/stop`.
- `DeProgressBar` (dans `buffett-ui.tsx`) affiche désormais « seed N · génération M » (au lieu de
  juste « génération M ») et un bouton « ⏹ Arrêter » à côté, toujours actif dès que
  `optProgress.active` est vrai. Après clic : bouton passe en « Arrêt demandé... » (désactivé) le
  temps que le seed en cours se termine.
- À l'arrêt : le run passe à `statut = "termine"` normalement (pas de nouveau statut), comme une
  convergence naturelle — aucun changement ailleurs dans l'UI (historique, détail de run, etc.).

### 4. Plafond génération/seed relevé

`Config.STARR_DE_MAX_GENERATIONS` : `2000` → `50_000`. Reste un garde-fou, jamais le critère
d'arrêt normal (déjà le cas aujourd'hui).

## Tests

- Unitaire : `optimize_portfolio_de` avec `should_stop` qui retourne `True` après le 1er seed →
  vérifie qu'un seul seed a tourné (pas de 2e), et que le résultat retourné est valide (même
  contrat que d'habitude : `W` fini, somme = 1).
- Unitaire : `optimize_portfolio_de` sans `should_stop` (ou qui retourne toujours `False`) avec un
  problème qui converge vite → vérifie que ça s'arrête bien un jour (pas de vraie boucle infinie
  dans le test, sinon le test ne terminerait jamais — utiliser un problème trivial à convergence
  rapide, comme les tests existants).
- Unitaire : écriture async — vérifier que `_on_new_best` retourne immédiatement (ne bloque pas)
  même si l'écriture DB sous-jacente est lente (mock avec `time.sleep`), et que la deuxième
  écriture pendant que la première est en cours est bien ignorée sans erreur.
- Manuel : démarrer un run, cliquer Arrêter, vérifier que ça s'arrête à la fin du seed en cours
  (pas au milieu), que le run passe à `termine`, et que l'allocation finale est cohérente.

## Hors scope

- Ne touche pas au bouton "Analyser un ticker précis" (Bouton 2, sans rapport avec le DE).
- Ne change pas le statut `BuffettRun` (reste `termine`/`en_cours`/`interrompu`/`erreur` — pas de
  nouvel état pour un arrêt manuel, cf. Objectif #3).
- Pas de limite de sécurité type "arrêt automatique après X heures" pour les seeds infinis — c'est
  l'utilisateur qui décide, via le bouton Stop, quand s'arrêter. Si un run tourne indéfiniment sans
  qu'on y touche, il continue indéfiniment (comportement voulu).
