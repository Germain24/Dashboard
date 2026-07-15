# Buffett — Affectation titre→broker & malus de cardinalité par lignes réelles

**Date** : 2026-07-14
**Statut** : ✅ implémenté et testé (TDD) le 2026-07-14 — 472 tests finance verts
**Bugfix post-livraison (2026-07-14)** : voir section « Bug spray + perf » en fin de doc.
**Fichiers touchés** : `backend/app/services/finance/buffett/optimizer.py`,
`backend/app/services/finance/buffett/config.py`,
`backend/tests/test_finance/test_cap_cardinality.py`

## Contexte & problème

L'optimiseur STARR/DE travaille au **niveau ticker** : il produit un vecteur de
poids `w` (simplexe, somme 1). L'étape `split_budget_to_brokers` projette ensuite
ces poids sur les brokers.

Aujourd'hui cette projection **réplique** chaque titre : tout titre disponible
chez un broker y reçoit un poids > 0 (chaque broker réalise indépendamment le
même profil `w` dans son budget). En conséquence :

- Un titre **partagé** (dispo chez BourseDirect *et* Trading212) est acheté chez
  **les deux** → il occupe une ligne chez chacun.
- Le malus de cardinalité compte la **disponibilité**
  (`counts = access.T @ (w >= min_position)`), donc ce titre partagé est compté
  **dans les deux** plafonds de 20 lignes/broker.
- Impossible de **cantonner** un titre partagé à un seul broker, alors qu'en
  réalité l'utilisateur peut décider de l'acheter uniquement via T212 et pas via
  BourseDirect.

**Objectif** : permettre le cantonnement réel (1 titre = 1 broker) et faire que
le malus compte les **lignes réellement déployées** — *une ligne à 0 % sur un
broker compte pour 0*.

Effet comportemental attendu et **assumé** : les titres partagés cessant d'être
comptés en double, la pression de cardinalité baisse ; l'optimiseur retiendra
probablement **plus de titres** qu'avant (jusqu'à ~20 lignes *réelles*/broker au
lieu d'être bridé par le double comptage). C'est l'effet voulu.

## Décisions de conception (validées)

1. **Portée** : affectation **réelle** — `split_budget_to_brokers` achète le
   titre partagé chez **un seul** broker ; l'autre broker est à 0 % pour ce titre.
2. **Débordement** : **strict 1-titre = 1-broker**. Si le poids cible dépasse le
   budget du broker affecté, on **plafonne** au budget dispo et l'excédent est
   **redéployé sur les autres titres du même broker** (dérive de poids acceptée,
   jamais de 2e broker pour un même titre).
3. **Heuristique d'affectation** : **minimiser la dérive de poids**. On affecte
   chaque titre au broker dont le **budget restant** absorbe le mieux son poids
   cible (le broker avec le plus de capacité € restante parmi ceux qui proposent
   le titre). Conséquence assumée : les lignes se concentrent sur les brokers à
   gros budget (pas d'équilibrage de lignes).
4. **Malus** : compte les **lignes déployées réelles** par broker (poids déployé
   > 0). Dérivé directement de l'affectation → malus ↔ relevé réel cohérents.
5. **Perf** : affectation gloutonne **exacte partout** (dans le malus DE *et* au
   déploiement). Surcoût = boucle Python par candidat, attendu négligeable face au
   calcul CVaR sur 8 000 scénarios qui domine — **à valider empiriquement**
   (fallback documenté si régression).
6. **`STARR_DE_POPSIZE`** : 128 → **515** (plus de directions de recherche par
   génération, DE moins bridé par la haute dimension).

`STARR_MAX_LINES_PER_BROKER` reste **20**. `STARR_CARD_BETA` reste **0.15**.

## Architecture

### Nouvelle fonction unique d'affectation (source de vérité)

```python
def assign_tickers_to_brokers(w, access, b_ratios, min_position) -> np.ndarray:
    """Affecte chaque titre pondéré (w >= min_position) à EXACTEMENT un broker.

    Heuristique min-dérive : les titres sont traités du plus gros poids au plus
    petit ; chacun va au broker (parmi ceux qui le proposent, budget > 0) ayant
    le plus de capacité € RESTANTE (b_ratios[j] − Σ w déjà affectés à j). Remplir
    chaque broker vers son budget minimise la dérive ET évite de laisser un broker
    à vide (anti-cash-oisif). Retourne un vecteur [n] : indice de broker par titre,
    -1 si non pondéré ou non plaçable (aucun broker dispo avec budget)."""
```

Algorithme :
1. `assign = -1` partout ; `remaining = b_ratios.copy()`.
2. Titres pondérés triés par `w` décroissant.
3. Pour chaque titre : brokers candidats = `{j : access[i,j] and b_ratios[j] > 0}`.
   Si vide → reste `-1` (non plaçable, ignoré). Sinon `j* = argmax remaining[j]`
   sur les candidats ; `assign[i] = j*` ; `remaining[j*] -= w[i]` (peut devenir
   négatif : le dépassement sera géré par redéploiement au déploiement).

Cette règle « plus de capacité restante » sert **à la fois** le min-dérive (chaque
broker se remplit vers son budget) et l'anti-starvation (un broker avec budget mais
sans titre encore affecté a la capacité restante maximale → attire le prochain
titre disponible).

### `split_budget_to_brokers` (réécrit)

Remplace la logique de réplication. Étapes :
1. `assign = assign_tickers_to_brokers(w, access, b_ratios, min_position)`.
2. Pour chaque broker `j` (budget > 0) :
   - `kept = {i : assign[i] == j}`.
   - Si `kept` non vide : `W[i,j] = b_ratios[j] · w[i] / Σ_{k∈kept} w[k]`
     (budget du broker réparti au prorata sur SES titres affectés ; le
     redéploiement de l'excédent est automatique via cette normalisation).
   - **Fallback anti-cash-oisif** (edge case rare) : si `kept` est vide alors que
     le broker a des titres disponibles (tous affectés ailleurs), replier sur un
     équipondéré de ses titres disponibles (comme le code actuel). C'est la seule
     exception au strict 1-titre-1-broker, pour ne pas laisser de budget oisif.
3. Retourne `W` [n_tickers × n_brokers, fraction du capital total].

### Malus dans `neg_obj_batch` (réécrit)

Remplace `counts = access_f.T @ (W >= min_position)` par un comptage des lignes
**réellement affectées**, candidat par candidat :

```python
if card_beta > 0:
    counts = np.zeros((num_b, W.shape[1]))
    for s in range(W.shape[1]):
        a = assign_tickers_to_brokers(W[:, s], access_inv, b_ratios, min_position)
        counts[:, s] = np.bincount(a[a >= 0], minlength=num_b)
    excess = counts - max_per_broker
    pen += np.where(excess > 0,
                    np.exp(np.minimum(card_beta * excess, 700.0)) - 1.0,
                    0.0).sum(axis=0)
```

`access_inv`, `b_ratios`, `min_position` sont déjà disponibles dans le scope de
`solve_starr_de`. Le malus opère sur les titres investissables (colonnes de `W`
normalisées, cohérent avec le déploiement).

### Fonction autonome `per_broker_cardinality_penalty`

Devient la version **assignment-aware** (single source of truth), signature élargie
avec `b_ratios` :

```python
def per_broker_cardinality_penalty(w, access, b_ratios, max_per_broker, beta,
                                   threshold) -> float:
    a = assign_tickers_to_brokers(w, access, b_ratios, threshold)
    counts = np.bincount(a[a >= 0], minlength=access.shape[1])
    excess = counts - max_per_broker
    return float(np.sum(np.where(excess > 0, np.exp(beta * excess) - 1.0, 0.0)))
```

Le batch de `neg_obj_batch` reste inline (vectorisé sur la population) mais partage
la **même sémantique** que cette fonction (testée). `cardinality_penalty` (variante
globale `max_lines`, non utilisée dans le chemin DE) est **inchangée**.

### Config

`STARR_DE_POPSIZE: int = 515` (était 128).

## Flux de données

```
w (simplexe, niveau ticker, DE)
  └─ assign_tickers_to_brokers(w, access_inv, b_ratios, min_position)
       ├─ [malus DE]  → bincount → counts/broker → exp-malus
       └─ [déploiement] split_budget_to_brokers → W [ticker × broker]
             └─ discretize_allocation (inchangé) → ordres réels par broker
```

## Cas limites

- **Titre non plaçable** (aucun broker dispo avec budget > 0) : `assign = -1`,
  ignoré du malus et du déploiement (pas de ligne, pas de cash).
- **Broker à vide après affectation** : fallback équipondéré sur ses titres
  disponibles (anti-cash-oisif) — rare, seule entorse au strict 1-titre-1-broker.
- **Débordement budget** : géré par la normalisation prorata (excédent redéployé
  sur les autres titres affectés au broker) → dérive de poids, jamais 2e broker.
- **`beta <= 0`** : malus = 0 (inchangé).
- **Micro-lignes** (`w < min_position`) : non pondérées → non affectées → ne
  comptent pas (inchangé conceptuellement).

## Tests

Fichier `test_cap_cardinality.py`. Les tests de `cap_stock_weights` et
`cardinality_penalty` (globale) sont **inchangés**. Ceux de
`per_broker_cardinality_penalty` changent de sémantique (signature + affectation) :

- **RÉÉCRIT** `test_per_broker_cardinality_counts_each_broker_separately` : 25
  titres partagés sur 2 brokers de budget égal → affectés strictement (~12/13 par
  broker) → **sous le cap → malus ≈ 0** (démontre la fin du double comptage).
- **CONSERVÉ (adapté signature)** `test_per_broker_cardinality_zero_under_cap` :
  15 exclusifs A + 15 exclusifs B → forcés chez leur broker → 15/15 → 0.
- **CONSERVÉ (adapté)** `test_per_broker_cardinality_ignores_sub_threshold` :
  micro-lignes ignorées → 0.
- **NOUVEAU** `test_shared_ticker_assigned_to_single_broker` : un titre partagé →
  affecté à un seul broker (ligne comptée une fois, 0 % chez l'autre).
- **NOUVEAU** `test_exclusive_ticker_forced_to_its_broker` : titre exclusif A →
  toujours chez A.
- **NOUVEAU** `test_min_drift_fills_brokers_toward_budget` : sur budgets inégaux,
  la somme des `w` affectés à chaque broker suit l'ordre des budgets (min-dérive).
- **NOUVEAU** `test_split_budget_no_idle_cash` : chaque broker ayant des titres
  disponibles déploie tout son budget (Σ W[:,j] ≈ b_ratios[j]).
- **NOUVEAU** `test_split_budget_zero_line_counts_zero` : un titre à 0 % déployé
  chez un broker n'y compte aucune ligne (le malus le reflète).
- **NOUVEAU** `test_overflow_redeployed_within_broker` : un titre dont le poids
  cible dépasse le budget du broker est plafonné, l'excédent redéployé sur les
  autres titres du même broker (aucun 2e broker).

Vérifier aussi la **non-régression perf** du DE : comparer le temps par génération
avant/après (le surcoût de la boucle d'affectation doit rester marginal). Si
régression notable, fallback = approximation vectorisée du comptage dans le DE
(affectation indépendante par argmax de budget), l'affectation exacte restant au
déploiement.

## Hors périmètre (YAGNI)

- Pas de reformulation ticker×broker dans le DE (dimension × n_brokers → trop lent).
- Pas d'équilibrage de lignes ni d'affectation optimale exacte (min-dérive gloutonne
  suffit).
- Pas de contrainte **dure** de cap 20/broker : le cap reste un malus **doux**
  (exponentiel), le comportement historique.

## Bug spray + perf (corrigé le 2026-07-14, même jour)

**Symptômes signalés** : (1) portefeuille avec des CENTAINES de micro-lignes à 0,1 %
(qui « devraient donner un giga malus » mais non), (2) graphique de score qui ne
s'affiche plus.

**Root cause (systematic-debugging)** : la DE choisit bien ~20 titres (tête propre
à 8 %). Les centaines de micro-lignes étaient un **artefact de déploiement**. Le
fallback anti-cash-oisif de `split_budget_to_brokers` se déclenchait dès qu'un broker
était **affamé** par le cantonnement min-dérive (budgets inégaux → tous les titres
≥ seuil affectés au plus gros broker) et **pulvérisait son budget uniformément sur
TOUT l'univers disponible** (~2000 titres). Ces micro-lignes ont un poids < seuil →
invisibles au malus (d'où « pas de malus »). Effet de bord : `discretize_allocation`
(boucle `for _ in range(1_000_000)` scannant tous les tickers) devenait quasi-infinie
sur un W de ~2000 lignes → la **finalisation hangeait** → `finish()` jamais appelé →
le graphe (polling) restait figé (2e symptôme).

**Fix** : le fallback d'un broker affamé déploie désormais sur ses **titres
disponibles ≥ seuil** (prorata `w`), l'équipondéré uniforme n'étant plus qu'un dernier
recours (aucun titre ≥ seuil dispo). Test de régression :
`test_starved_broker_does_not_spray_junk`.

**Vérif end-to-end** (150 titres, 3 brokers budgets 9000/4000/500 pour forcer la
starvation) : 37 lignes déployées (vs centaines), `discretize` 0,04 s (vs hang),
`progress_cb` appelé 1907× avec des scores finis (graphe OK).

**Perf** : `assign_tickers_to_brokers` réécrit en Python pur (listes au lieu
d'indexation numpy scalaire / `np.argmax`) — **6,9× plus rapide** (162,8 s → 23,7 s
pour 244k appels), comportement identique. La boucle de malus par candidat repasse à
~1-2 % du temps DE (au lieu de ~8 % au repro, ~15-30 min à l'échelle prod).

## Bugfix n°2 : dernier recours plafonné + graphe STARR en vue détail (2026-07-15)

**Symptômes (run 39, code déjà corrigé)** : toujours ~400 « 1 action Bourso » dans le
tableau live, et pas de graphe STARR.

**Root cause 1 (allocation)** : le premier fix couvrait le broker affamé AVEC des
titres dispo >= seuil, mais son **dernier recours** (aucun titre dispo >= seuil, ex.
candidat DE mono-ETF dispo uniquement chez T212 — visible : « ISPA.DE 100 % pie
T212 ») pulvérisait encore équipondéré sur TOUT l'univers dispo (~2000 lignes).
**Fix** : fallback unifié — dispos >= seuil, sinon tous les dispos — trié par poids
décroissant et **plafonné à `fallback_max_lines`** (défaut
`Config.STARR_MAX_LINES_PER_BROKER` = 20). Plus jamais >20 lignes de fallback, quel
que soit le candidat. Tests : `test_starved_broker_no_weighted_dispo_is_capped`,
`test_starved_broker_many_weighted_dispo_also_capped`.

**Root cause 2 (graphe)** : le graphe n'était monté QUE sur la vue liste de l'onglet
Buffett (`BuffettTab`) ; ouvrir le détail du run (`BuffettRunDetailView`, là où vit le
tableau « Allocation cible ») REMPLACE l'onglet -> graphe invisible alors que le
backend émettait bien `best_score` (vérifié : iteration 1498, score -0.97 → -0.72).
**Fix** : `optProgress` passé à la vue détail, `DeStarrChart` rendu sous la bannière
« Optimisation en cours » (gardé par `run_id === selected.run.id`).

Vérifs : backend 21/21 (split+cardinalité) + optimizer_robust ; frontend tsc propre,
222/222 tests.
