# Score relatif au benchmark CW8.PA — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les étapes
> utilisent la syntaxe case à cocher (`- [ ]`).

**Objectif :** remplacer l'objectif d'optimisation `STARR = rendement / risque` par un
score relatif au benchmark CW8.PA, et remplacer le prior de rendement (médiane
globale) par un prior par classe d'actif — pour que l'optimiseur cesse d'allouer
96 % à un ETF monétaire.

**Architecture :** trois fonctions pures nouvelles et testables isolément
(`load_asset_classes`, `class_aware_prior`, `neg_benchmark_relative[_batch]`), puis
leur câblage dans `optimize_portfolio_de`. Le benchmark n'appartenant pas à l'univers
d'optimisation, ses rendements sont injectés par le runner et simulés comme colonne
supplémentaire.

**Stack :** Python 3.12, numpy, scipy (`DifferentialEvolutionSolver`), pandas,
pytest. Tests dans `backend/tests/test_finance/`.

**Spec :** `orchestration/a-faire/2026-07-21-buffett-score-relatif-benchmark-design.md`

## Contraintes globales

- Commande de test : `cd backend && uv run pytest <chemin> -v`
- Toute nouvelle fonction publique porte une docstring en **français** expliquant le
  *pourquoi*, comme le reste du module.
- **Pas de LaTeX** ni de formules unicode dans les commentaires : ASCII simple.
- Les pénalités de l'objectif restent **additives**. Ne jamais introduire de
  pénalité multiplicative : le score est centré sur 0, et `0 × malus = 0` rendrait
  les violations invisibles.
- `STARR_MEAN_SIGNAL_WEIGHT` reste à **0,25** : on change vers *quoi* on tire, pas
  *de combien*.
- Le score final est exprimé en **points de pourcentage annuels** (× 100), pour que
  les coefficients de pénalité existants restent du bon ordre de grandeur.
- Ne pas toucher : copules, `simulate_regime_scenarios`, contraintes look-through,
  discrétisation par broker, filtre de liquidité.

---

### Task 1 : `load_asset_classes()` — classification des actifs

**Fichiers :**
- Modifier : `backend/app/services/finance/buffett/broker_availability.py`
- Test : `backend/tests/test_finance/test_asset_classes.py` (créer)

**Interfaces :**
- Consomme : `_find_ticker_col`, `_norm_ticker`, `_secteur1_col`, `load_broker_table`
  (déjà présents dans le module).
- Produit : `load_asset_classes(df=None, ticker_col="Ticker Yahoo Finance") -> dict[str, str]`
  — ticker MAJUSCULE → l'une de `"taux"`, `"actions"`, `"matieres_premieres"`. Un
  ticker de classe inconnue est **absent** du dict.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/test_finance/test_asset_classes.py` :

```python
"""Classification des actifs depuis la colonne 'Secteur 2' de ToutBroker."""

import pandas as pd


def _df(rows):
    return pd.DataFrame(rows, columns=["Ticker Yahoo Finance", "Secteur 1", "Secteur 2"])


def test_obligations_et_monetaire_fusionnes_en_taux():
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["OBLI.PA", "ETF", "Monétaire"], ["IGLT.L", "ETF", "Obligations"]])
    assert load_asset_classes(df) == {"OBLI.PA": "taux", "IGLT.L": "taux"}


def test_mojibake_du_tableur_reconnu():
    """Le fichier réel contient des accents cassés : la reconnaissance se fait par
    préfixe désaccentué, sinon Monétaire et Matières premières tombent dans actions."""
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["A", "ETF", "Mon�taire"], ["B", "ETF", "Mati�res premi�res"]])
    assert load_asset_classes(df) == {"A": "taux", "B": "matieres_premieres"}


def test_actions_et_secteurs_individuels():
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["C", "ETF", "Actions"], ["D", "Technologie", "Logiciels et services"]])
    assert load_asset_classes(df) == {"C": "actions", "D": "actions"}


def test_titre_vif_sans_secteur2_est_une_action():
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["E", "Santé", ""], ["F", "Technologie", None]])
    assert load_asset_classes(df) == {"E": "actions", "F": "actions"}


def test_etf_sans_secteur2_est_absent_du_dict():
    """Classe inconnue -> l'optimiseur retombe sur la médiane globale."""
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["G", "ETF", ""], ["H", "ETF", "Actions"]])
    assert load_asset_classes(df) == {"H": "actions"}


def test_reset_cache_invalide_les_classes():
    from app.services.finance.buffett import broker_availability as ba
    ba._ASSET_CLASS_CACHE = {"STALE": "actions"}
    ba.reset_etf_cache()
    assert ba._ASSET_CLASS_CACHE is None
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```
cd backend && uv run pytest tests/test_finance/test_asset_classes.py -v
```
Attendu : ÉCHEC, `ImportError: cannot import name 'load_asset_classes'`.

- [ ] **Étape 3 : implémenter**

Dans `broker_availability.py`, juste après `_secteur1_col` (l.65) :

```python
def _secteur2_col(columns) -> str | None:
    """Trouve la colonne 'Secteur 2' (tolère espaces/casse)."""
    for c in columns:
        if str(c).strip().lower() == "secteur 2":
            return c
    return None


def _normalize_asset_class(secteur2, secteur1) -> str | None:
    """Classe d'actif depuis 'Secteur 2'. None = inconnue.

    Obligations et Monétaire sont FUSIONNÉS en `taux` (décision utilisateur
    2026-07-21) : le monétaire ne comptait qu'un titre, et son comportement est
    celui d'un produit de taux.

    La comparaison se fait sur un PRÉFIXE désaccentué et jamais sur la chaîne
    complète : le tableur contient du mojibake (`Mati?res premi?res`,
    `Mon?taire`) qui ferait silencieusement tomber ces classes dans `actions`.
    """
    import unicodedata

    norm = (
        unicodedata.normalize("NFKD", str(secteur2).strip())
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    if norm in ("", "nan", "none"):
        # Un titre vif sans Secteur 2 est une action ; un ETF sans Secteur 2 a une
        # classe réellement inconnue -> repli sur la médiane globale.
        return None if str(secteur1).strip().upper() == "ETF" else "actions"
    if norm.startswith("oblig") or norm.startswith("mon"):
        return "taux"
    if norm.startswith("mati"):
        return "matieres_premieres"
    return "actions"


def _compute_asset_classes(df, ticker_col: str) -> dict[str, str]:
    if df is None or getattr(df, "empty", True):
        return {}
    tcol = _find_ticker_col(df.columns, ticker_col)
    s2col = _secteur2_col(df.columns)
    s1col = _secteur1_col(df.columns)
    if tcol is None or s2col is None:
        return {}
    s1_values = df[s1col] if s1col is not None else ["" for _ in range(len(df))]
    out: dict[str, str] = {}
    for t, s2, s1 in zip(df[tcol], df[s2col], s1_values, strict=True):
        tt = _norm_ticker(t)
        if not tt:
            continue
        klass = _normalize_asset_class(s2, s1)
        if klass is not None:
            out[tt] = klass
    return out


def load_asset_classes(df=None, ticker_col: str = "Ticker Yahoo Finance") -> dict[str, str]:
    """Classe d'actif par ticker depuis ToutBroker.xlsx ('Secteur 2').

    Source AUTORITAIRE, comme `load_etf_tickers` l'est pour la classification ETF.
    Sert au prior de rendement de l'optimiseur : chaque titre est tiré vers la
    médiane de SA classe et non vers celle de tout l'univers, qui offrait ~9 points
    de rendement fictif aux obligations. `df` explicite = pas de cache (tests).
    """
    global _ASSET_CLASS_CACHE
    if df is not None:
        return _compute_asset_classes(df, ticker_col)
    if _ASSET_CLASS_CACHE is None:
        _ASSET_CLASS_CACHE = _compute_asset_classes(load_broker_table(), ticker_col)
    return _ASSET_CLASS_CACHE
```

Ajouter la variable de cache à côté de `_ETF_CACHE` / `_UNIVERSE_CACHE` (l.89-90) :

```python
_ASSET_CLASS_CACHE: dict[str, str] | None = None
```

Et l'invalider dans `reset_etf_cache` (l.93-97) :

```python
def reset_etf_cache() -> None:
    """Invalide les caches ETF/univers/classes (à appeler après modif de ToutBroker.xlsx)."""
    global _ETF_CACHE, _UNIVERSE_CACHE, _ASSET_CLASS_CACHE
    _ETF_CACHE = None
    _UNIVERSE_CACHE = None
    _ASSET_CLASS_CACHE = None
```

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```
cd backend && uv run pytest tests/test_finance/test_asset_classes.py -v
```
Attendu : 6 passed.

- [ ] **Étape 5 : vérifier sur les données réelles**

```
cd backend && .venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'.'); from app.services.finance.buffett.broker_availability import load_asset_classes; import collections; c=load_asset_classes(); print(collections.Counter(c.values())); print('OBLI.PA ->', c.get('OBLI.PA'))"
```
Attendu : `OBLI.PA -> taux`, et un compte `taux` de l'ordre de 430+.

- [ ] **Étape 6 : commit**

```bash
git add backend/app/services/finance/buffett/broker_availability.py backend/tests/test_finance/test_asset_classes.py
git commit -m "feat(buffett): classification des actifs par classe (Secteur 2 de ToutBroker)"
```

---

### Task 2 : `class_aware_prior()` — prior de rendement par classe

**Fichiers :**
- Modifier : `backend/app/services/finance/buffett/optimizer.py` (ajouter la fonction
  juste avant `optimize_portfolio_de`, l.600)
- Test : `backend/tests/test_finance/test_class_aware_prior.py` (créer)

**Interfaces :**
- Consomme : rien (fonction pure sur numpy).
- Produit : `class_aware_prior(raw_mean_daily, classes) -> np.ndarray` — `classes`
  est une séquence alignée **index par index** sur `raw_mean_daily`, `None` valant
  « classe inconnue ». Retourne un vecteur de même longueur.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/test_finance/test_class_aware_prior.py` :

```python
"""Prior de rendement : médiane de la CLASSE et non médiane globale."""

import numpy as np


def test_obligation_nest_plus_tiree_vers_la_mediane_des_actions():
    """Le bug d'origine : une obligation à 3,5 % recevait ~12,7 % espérés."""
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.02, 0.03, 0.20, 0.22, 0.24])       # 2 titres de taux, 3 actions
    classes = ["taux", "taux", "actions", "actions", "actions"]
    prior = class_aware_prior(mu, classes)
    assert prior[0] == prior[1] == 0.025                # médiane des taux
    assert prior[2] == prior[3] == prior[4] == 0.22     # médiane des actions


def test_ordre_intra_classe_preserve():
    """Le prior est un centre de gravité, pas une valeur imposée."""
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.01, 0.03, 0.05])
    prior = class_aware_prior(mu, ["taux"] * 3)
    estim = 0.25 * mu + 0.75 * prior
    assert estim[0] < estim[1] < estim[2]


def test_classe_singleton_vaut_sa_propre_moyenne():
    """Pas de taille minimale : un seuil ferait retomber sur la médiane globale."""
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.01, 0.20, 0.30])
    prior = class_aware_prior(mu, ["taux", "actions", "actions"])
    assert prior[0] == 0.01


def test_classe_inconnue_retombe_sur_la_mediane_globale():
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.01, 0.20, 0.30, 0.40])
    prior = class_aware_prior(mu, ["taux", "actions", "actions", None])
    assert prior[3] == float(np.median(mu))


def test_valeurs_non_finies_ignorees_dans_la_mediane():
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.02, np.nan, 0.04])
    prior = class_aware_prior(mu, ["taux", "taux", "taux"])
    assert prior[0] == 0.03
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```
cd backend && uv run pytest tests/test_finance/test_class_aware_prior.py -v
```
Attendu : ÉCHEC, `ImportError: cannot import name 'class_aware_prior'`.

- [ ] **Étape 3 : implémenter**

Dans `optimizer.py`, immédiatement avant `def optimize_portfolio_de(` (l.600) :

```python
def class_aware_prior(raw_mean_daily, classes) -> np.ndarray:
    """Prior de rendement journalier : la médiane de la CLASSE de chaque titre.

    Remplace la médiane globale unique, qui tirait les obligations vers la médiane
    de tout l'univers (15,79 %/an mesuré) et leur offrait ainsi ~9 points de
    rendement fictif tout en leur laissant leur risque quasi nul.

    Le shrinkage lui-même reste indispensable : mesuré sur 2145 titres, le
    rendement passé ne prédit pas le rendement futur (Pearson 0,001) alors que le
    risque, lui, persiste (Spearman 0,935). Sans régularisation l'optimiseur
    achèterait des titres dont l'avantage s'évapore et dont le risque reste. Mais
    l'écart ENTRE CLASSES est structurel et persiste (taux 4,32 -> 5,52 %, actions
    13,32 -> 18,13 % d'un semestre à l'autre) : c'est le bon groupe de pairs.

    `classes` est aligné index par index sur `raw_mean_daily` ; `None` = classe
    inconnue -> médiane globale (comportement historique).

    PAS de taille minimale de classe : une classe à un seul membre dégénère en sa
    propre moyenne, ce qui pour une obligation est la réponse conservatrice
    correcte. Un seuil minimal ferait retomber les petites classes sur la médiane
    globale, c'est-à-dire réintroduirait le bug d'origine.
    """
    mu = np.asarray(raw_mean_daily, dtype=float)
    finite_all = mu[np.isfinite(mu)]
    global_median = float(np.median(finite_all)) if finite_all.size else 0.0
    prior = np.full(mu.shape, global_median, dtype=float)
    labels = list(classes)
    for name in {c for c in labels if c is not None}:
        mask = np.array([c == name for c in labels], dtype=bool)
        values = mu[mask]
        finite = values[np.isfinite(values)]
        if finite.size:
            prior[mask] = float(np.median(finite))
    return prior
```

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```
cd backend && uv run pytest tests/test_finance/test_class_aware_prior.py -v
```
Attendu : 5 passed.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/services/finance/buffett/optimizer.py backend/tests/test_finance/test_class_aware_prior.py
git commit -m "feat(buffett): prior de rendement par classe d'actif"
```

---

### Task 3 : nouveau score relatif au benchmark

**Fichiers :**
- Modifier : `backend/app/services/finance/buffett/starr.py` (ajouter après
  `neg_starr_batch`, l.479)
- Modifier : `backend/app/services/finance/buffett/config.py` (l.156-158)
- Test : `backend/tests/test_finance/test_benchmark_relative_score.py` (créer)

**Interfaces :**
- Consomme : `portfolio_cvar`, `downside_deviation` (déjà dans `starr.py`).
- Produit :
  - `benchmark_stats(bench_sim_returns, bench_mean_daily, alpha=0.05, target=0.0) -> dict`
    avec les clés `annual_return`, `cvar`, `downside_deviation` (toutes annualisées,
    en **fraction**).
  - `neg_benchmark_relative(raw_weights, sim_rets, mean_daily, bench, alpha=0.05, downside_weight=1.0, target=0.0, annual_cost=0.0) -> float`
  - `neg_benchmark_relative_batch(raw_weights, sim_rets, mean_daily, bench, alpha=0.05, downside_weight=1.0, target=0.0, annual_costs=0.0) -> np.ndarray`
  - Les deux retournent l'**opposé** du score (convention de minimisation), en
    points de pourcentage annuels.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/test_finance/test_benchmark_relative_score.py` :

```python
"""Score relatif au benchmark : excédent de rendement moins l'EXCÈS de risque."""

import numpy as np


def _fixture():
    """3 actifs : 0 = clone du benchmark, 1 = plus risqué, 2 = moins risqué."""
    rng = np.random.default_rng(7)
    bench = rng.normal(0.0005, 0.01, 4000)
    sim = np.column_stack([bench, bench * 2.0, bench * 0.25])
    mean_daily = np.array([0.0005, 0.0010, 0.000125])
    return sim, mean_daily, bench


def test_portefeuille_identique_au_benchmark_score_zero():
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    score = -neg_benchmark_relative(np.array([1.0, 0.0, 0.0]), sim, mean_daily, b)
    assert abs(score) < 1e-6


def test_moins_risque_que_le_benchmark_ne_donne_aucun_bonus():
    """max(0, ...) : c'est ce qui empêche le retour du biais obligataire."""
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    score = -neg_benchmark_relative(np.array([0.0, 0.0, 1.0]), sim, mean_daily, b)
    # rendement 4x plus faible, risque 4x plus faible -> seul le deficit compte
    expected = (0.000125 - 0.0005) * 252.0 * 100.0
    assert abs(score - expected) < 1e-6


def test_exces_de_risque_est_soustrait_et_non_ajoute():
    """Garde-fou anti-inversion de signe : additionner l'excès récompenserait le risque."""
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    risque = -neg_benchmark_relative(np.array([0.0, 1.0, 0.0]), sim, mean_daily, b)
    exces_rendement = (0.0010 - 0.0005) * 252.0 * 100.0
    assert risque < exces_rendement    # l'exces de risque a bien ete retranche


def test_frais_reduisent_le_score():
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    w = np.array([1.0, 0.0, 0.0])
    sans = -neg_benchmark_relative(w, sim, mean_daily, b)
    avec = -neg_benchmark_relative(w, sim, mean_daily, b, annual_cost=0.01)
    assert abs((sans - avec) - 1.0) < 1e-6      # 1 % de frais = 1 point


def test_batch_coherent_avec_le_scalaire():
    from app.services.finance.buffett.starr import (
        benchmark_stats, neg_benchmark_relative, neg_benchmark_relative_batch,
    )
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    W = np.array([[1.0, 0.0, 0.5], [0.0, 1.0, 0.5], [0.0, 0.0, 0.0]])
    lot = neg_benchmark_relative_batch(W, sim, mean_daily, b)
    for j in range(W.shape[1]):
        assert abs(lot[j] - neg_benchmark_relative(W[:, j], sim, mean_daily, b)) < 1e-6


def test_poids_nuls_renvoient_la_penalite_max():
    from app.services.finance.buffett.starr import benchmark_stats, neg_benchmark_relative
    sim, mean_daily, bench = _fixture()
    b = benchmark_stats(bench, 0.0005)
    assert neg_benchmark_relative(np.zeros(3), sim, mean_daily, b) == 1e6
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```
cd backend && uv run pytest tests/test_finance/test_benchmark_relative_score.py -v
```
Attendu : ÉCHEC, `ImportError: cannot import name 'benchmark_stats'`.

- [ ] **Étape 3 : implémenter le score**

À la fin de `starr.py` :

```python
SCORE_SCALE = 100.0   # score exprime en POINTS de pourcentage annuels


def benchmark_stats(bench_sim_returns, bench_mean_daily, alpha: float = 0.05,
                    target: float = 0.0) -> dict:
    """Reperes du benchmark, calcules UNE SEULE FOIS avant la boucle DE.

    `bench_sim_returns` doit provenir des MEMES scenarios simules que les
    candidats (colonne dediee de `sim_rets`), sans quoi la comparaison melangerait
    deux tirages differents.
    """
    return {
        "annual_return": float(bench_mean_daily) * 252.0,
        "cvar": float(portfolio_cvar(bench_sim_returns, alpha)) * np.sqrt(252.0),
        "downside_deviation": float(
            downside_deviation(bench_sim_returns, target)
        ) * np.sqrt(252.0),
    }


def neg_benchmark_relative(raw_weights: np.ndarray, sim_rets: np.ndarray,
                           mean_daily: np.ndarray, bench: dict,
                           alpha: float = 0.05, downside_weight: float = 1.0,
                           target: float = 0.0, annual_cost: float = 0.0) -> float:
    """-(score) pour la minimisation. `raw_weights` normalise sur le simplexe.

    score = (rendement - rendement_benchmark)
          - max(0, CVaR - CVaR_benchmark)
          - lambda * max(0, semi-deviation - semi-deviation_benchmark)

    Trois proprietes voulues :
    - un portefeuille identique au benchmark vaut exactement 0 ;
    - PLUS de division, donc plus de score infini quand le CVaR tend vers 0 : c'est
      ce qui permettait a un ETF monetaire de rafler 96 % de l'allocation ;
    - etre MOINS risque que le benchmark ne rapporte rien (`max(0, ...)`), sans quoi
      le biais monetaire reviendrait par la porte du denominateur.

    La semi-deviation ne compte que les journees NEGATIVES : la volatilite a la
    hausse n'est jamais penalisee.
    """
    s = float(np.sum(raw_weights))
    if s <= 1e-12:
        return 1e6
    w = raw_weights / s
    ann_ret = float(mean_daily @ w) * 252.0 - max(float(annual_cost), 0.0)
    port = sim_rets @ w
    cvar = portfolio_cvar(port, alpha) * np.sqrt(252.0)
    dd = downside_deviation(port, target) * np.sqrt(252.0)
    score = (
        (ann_ret - bench["annual_return"])
        - max(0.0, cvar - bench["cvar"])
        - downside_weight * max(0.0, dd - bench["downside_deviation"])
    )
    if not np.isfinite(score):
        return 1e6
    return -score * SCORE_SCALE


def neg_benchmark_relative_batch(raw_weights: np.ndarray, sim_rets: np.ndarray,
                                 mean_daily: np.ndarray, bench: dict,
                                 alpha: float = 0.05, downside_weight: float = 1.0,
                                 target: float = 0.0, annual_costs=0.0) -> np.ndarray:
    """Version VECTORISEE sur une population entiere.

    `raw_weights` : [n_actifs x S], une colonne par candidat (convention scipy
    `vectorized=True`). Meme estimation du CVaR par `np.partition` que
    `neg_starr_batch` : moyenne des `round(alpha * n_sim)` pires scenarios.
    """
    X = np.asarray(raw_weights, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    n_sim = sim_rets.shape[0]
    out = np.full(X.shape[1], 1e6)
    X = np.maximum(X, 0.0)
    s = X.sum(axis=0)
    ok = s > 1e-12
    if not ok.any():
        return out
    W = X[:, ok] / s[ok]
    cost_array = np.broadcast_to(
        np.asarray(annual_costs, dtype=float), (X.shape[1],)
    )[ok]
    ann_ret = (mean_daily @ W) * 252.0 - np.maximum(cost_array, 0.0)
    port = sim_rets @ W.astype(sim_rets.dtype)
    k = max(1, int(round(alpha * n_sim)))
    tail = np.partition(port, k - 1, axis=0)[:k]
    cvar = -tail.mean(axis=0, dtype=np.float64) * np.sqrt(252.0)
    downside = np.minimum(port - target, 0.0).astype(np.float64)
    dd = np.sqrt(np.mean(downside ** 2, axis=0)) * np.sqrt(252.0)
    score = (
        (ann_ret - bench["annual_return"])
        - np.maximum(cvar - bench["cvar"], 0.0)
        - downside_weight * np.maximum(dd - bench["downside_deviation"], 0.0)
    )
    out[ok] = np.where(np.isfinite(score), -score * SCORE_SCALE, 1e6)
    return out
```

- [ ] **Étape 4 : ajouter les réglages de configuration**

Dans `config.py`, remplacer le bloc turnover (l.154-158) :

```python
    # Benchmark de reference : le score mesure l'ecart A CE TITRE. Il n'appartient
    # PAS a l'univers d'optimisation (select_etfs_per_broker l'ecarte) : ses
    # rendements sont injectes par le runner. Cf. la spec du 2026-07-21.
    STARR_BENCHMARK_TICKER: str = "CW8.PA"
    REBALANCES_PER_YEAR: int = 4
```

(Les lignes `STARR_TURNOVER_PENALTY` et `STARR_REBALANCE_BAND_PCT` disparaissent :
elles faisaient doublon avec les frais de transaction, qui modelisent deja le cout
des ordres.)

Et abaisser le nombre de seeds (l.100) :

```python
    STARR_DE_MAX_SEEDS: int = 1
```

- [ ] **Étape 5 : lancer les tests et vérifier qu'ils passent**

```
cd backend && uv run pytest tests/test_finance/test_benchmark_relative_score.py -v
```
Attendu : 6 passed.

- [ ] **Étape 6 : commit**

```bash
git add backend/app/services/finance/buffett/starr.py backend/app/services/finance/buffett/config.py backend/tests/test_finance/test_benchmark_relative_score.py
git commit -m "feat(buffett): score relatif au benchmark (remplace le ratio STARR)"
```

---

### Task 4 : injection des rendements du benchmark

**Fichiers :**
- Modifier : `backend/app/services/finance/buffett/runner.py:613` et `:648`
- Modifier : `backend/app/services/finance/buffett/optimizer.py` (signature de
  `optimize_portfolio_de`, l.600-621)
- Test : `backend/tests/test_finance/test_benchmark_injection.py` (créer)

**Interfaces :**
- Consomme : `Config.STARR_BENCHMARK_TICKER` (Task 3), `returns_in_base_currency`
  (déjà dans `dedup.py`).
- Produit : `optimize_portfolio_de(..., benchmark_returns=None)` — nouveau paramètre
  nommé, `pd.Series` indexée par date. Lève `ValueError` si absent.

- [ ] **Étape 1 : écrire le test qui échoue**

Créer `backend/tests/test_finance/test_benchmark_injection.py` :

```python
"""Le benchmark n'est pas dans l'univers : il doit être injecté explicitement."""

import numpy as np
import pandas as pd
import pytest


def test_absence_de_benchmark_leve_une_erreur_explicite():
    """Un score mesuré contre un benchmark absent n'aurait aucun sens : on échoue
    bruyamment plutôt que de retomber sur un benchmark nul."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    rets = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (800, 3)))
    with pytest.raises(ValueError, match="benchmark"):
        optimize_portfolio_de(
            ["A", "B", "C"], rets, [[True], [True], [True]], ["Trading212"],
            benchmark_returns=None,
        )


def test_benchmark_trop_court_leve_une_erreur():
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    rets = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (800, 3)))
    court = pd.Series(np.random.default_rng(1).normal(0, 0.01, 10))
    with pytest.raises(ValueError, match="benchmark"):
        optimize_portfolio_de(
            ["A", "B", "C"], rets, [[True], [True], [True]], ["Trading212"],
            benchmark_returns=court,
        )
```

- [ ] **Étape 2 : lancer le test et vérifier qu'il échoue**

```
cd backend && uv run pytest tests/test_finance/test_benchmark_injection.py -v
```
Attendu : ÉCHEC — `TypeError: optimize_portfolio_de() got an unexpected keyword
argument 'benchmark_returns'`.

- [ ] **Étape 3 : ajouter le paramètre et la validation**

Dans `optimizer.py`, ajouter à la signature de `optimize_portfolio_de` (après
`ttf_tickers`, l.619) :

```python
    benchmark_returns=None,   # pd.Series de rendements EUR du benchmark
```

Puis, tout au début du corps (juste après les imports locaux, avant le calcul de
`n_sim`) :

```python
    # Le benchmark n'appartient PAS a l'univers d'optimisation : verifie sur le run
    # #51, select_etfs_per_broker l'ecarte (855 ETF -> 58). Ses rendements sont donc
    # injectes par le runner. Sans lui le score n'a aucun sens -> echec explicite.
    if benchmark_returns is None or len(benchmark_returns) < 2:
        raise ValueError(
            f"benchmark introuvable ({Config.STARR_BENCHMARK_TICKER}) : "
            "le score relatif ne peut pas etre calcule"
        )
    bench_series = np.asarray(benchmark_returns, dtype=float)
    if len(bench_series) < int(Config.STARR_MIN_HISTORY_DAYS):
        raise ValueError(
            f"benchmark {Config.STARR_BENCHMARK_TICKER} : "
            f"{len(bench_series)} jours < {Config.STARR_MIN_HISTORY_DAYS} requis"
        )
```

- [ ] **Étape 4 : extraire le benchmark côté runner**

Dans `runner.py`, remplacer la ligne 613 :

```python
        t_list = list(eligible.keys())
```

par :

```python
        # Le benchmark doit etre telecharge meme s'il n'est pas eligible : c'est la
        # reference du score, pas un candidat a l'allocation.
        bench_ticker = str(Config.STARR_BENCHMARK_TICKER).strip().upper()
        t_list = list(eligible.keys())
        if bench_ticker and bench_ticker not in {t.upper() for t in t_list}:
            t_list.append(bench_ticker)
```

Puis, juste apres la ligne 648 (`rets = cd.pct_change()...`), AVANT toute etape de
deduplication :

```python
                # Extraction du benchmark AVANT dedup/selection : ces etapes peuvent
                # l'ecarter (jumeau d'indice, plafond de 50 ETF/broker) alors qu'il
                # doit rester la reference du score.
                bench_rets = None
                bench_col = next(
                    (c for c in rets.columns if str(c).upper() == bench_ticker), None
                )
                if bench_col is not None:
                    bench_rets = returns_in_base_currency(
                        rets[[bench_col]], "EUR", strict=True
                    )[bench_col]
                    print(f"[runner] Benchmark {bench_ticker} : {len(bench_rets)} jours")
                else:
                    print(f"[runner] ATTENTION : benchmark {bench_ticker} absent des cours")
```

Enfin, transmettre le parametre a l'appel de `optimize_portfolio_de` (rechercher
`optimize_portfolio_de(` dans `runner.py`) en ajoutant :

```python
                    benchmark_returns=bench_rets,
```

- [ ] **Étape 5 : lancer les tests et vérifier qu'ils passent**

```
cd backend && uv run pytest tests/test_finance/test_benchmark_injection.py -v
```
Attendu : 2 passed.

- [ ] **Étape 6 : commit**

```bash
git add backend/app/services/finance/buffett/runner.py backend/app/services/finance/buffett/optimizer.py backend/tests/test_finance/test_benchmark_injection.py
git commit -m "feat(buffett): injection explicite des rendements du benchmark"
```

---

### Task 5 : câblage dans `optimize_portfolio_de`

**Fichiers :**
- Modifier : `backend/app/services/finance/buffett/optimizer.py` — blocs l.643-648
  (imports), l.672-682 (prior), l.697-710 (simulation), l.730-740 (turnover),
  l.945-988 (`neg_obj_batch`), l.998 (`ticker_standalone_scores`), l.1264-1275
  (`_full_starr`)
- Test : mise à jour de `backend/tests/test_finance/test_optimizer_robust.py`

**Interfaces :**
- Consomme : `class_aware_prior` (Task 2), `benchmark_stats` /
  `neg_benchmark_relative[_batch]` (Task 3), `benchmark_returns` (Task 4),
  `load_asset_classes` (Task 1).
- Produit : `optimize_portfolio_de` retourne `(W, score, diagnostics?)` où `score`
  est désormais en points de pourcentage annuels (et non plus un ratio).

- [ ] **Étape 1 : simuler le benchmark conjointement**

Remplacer le bloc de simulation (l.697-710) pour ajouter le benchmark en **dernière
colonne** de la matrice simulée :

```python
    R_inv = R[:, inv_idx]
    mean_daily = mean_daily_all[inv_idx]
    access_inv = access[inv_idx]
    # Le benchmark est simule AVEC l'univers (memes scenarios, memes dependances de
    # queue) mais reste hors des variables de decision : derniere colonne.
    bench_aligned = bench_series[-R_inv.shape[0]:]
    if len(bench_aligned) < R_inv.shape[0]:
        pad = np.zeros(R_inv.shape[0] - len(bench_aligned))
        bench_aligned = np.concatenate([pad, bench_aligned])
    R_sim = np.column_stack([R_inv, bench_aligned])
    print(
        f"    * Score relatif a {Config.STARR_BENCHMARK_TICKER} : {len(inv_idx)} titres, "
        f"{n_sim} scenarios (Monte-Carlo + copule, CVaR {int(alpha * 100)} %)..."
    )
    sim_full, regime_diagnostics = simulate_regime_scenarios(
        R_sim,
        n_sim=n_sim,
        seed=seed,
        windows=Config.STARR_REGIME_WINDOWS,
        min_coverage=Config.STARR_REGIME_MIN_COVERAGE,
    )
    sim_rets = sim_full[:, :-1]
    bench_sim = sim_full[:, -1]
    bench_mean_daily = float(np.mean(bench_aligned[-min(len(bench_aligned), mean_window_days):]))
    bench = benchmark_stats(bench_sim, bench_mean_daily, alpha, 0.0)
    print(
        f"    * Benchmark : rendement {bench['annual_return'] * 100:.2f} %, "
        f"CVaR {bench['cvar'] * 100:.2f} %, baisse {bench['downside_deviation'] * 100:.2f} %"
    )
```

Ajouter `benchmark_stats`, `neg_benchmark_relative`, `neg_benchmark_relative_batch`
à l'import depuis `.starr` (l.643-648) et retirer `neg_starr`, `neg_starr_batch`.

- [ ] **Étape 2 : brancher le prior par classe**

Remplacer les lignes 676-681 :

```python
    mean_signal_weight = min(max(float(Config.STARR_MEAN_SIGNAL_WEIGHT), 0.0), 1.0)
    from .broker_availability import load_asset_classes

    asset_classes = load_asset_classes()
    ticker_classes = [asset_classes.get(str(t).upper()) for t in tickers]
    prior_daily = class_aware_prior(raw_mean_daily, ticker_classes)
    mean_daily_all = (
        mean_signal_weight * raw_mean_daily
        + (1.0 - mean_signal_weight) * prior_daily
    )
```

- [ ] **Étape 3 : supprimer la pénalité de turnover**

Supprimer les lignes 739-740 (`turnover_lambda`, `rebalance_band`) et, dans
`neg_obj_batch`, le bloc l.983-986 :

```python
            if has_current_weights and turnover_lambda > 0:
                changes = np.maximum(np.abs(W - current_inv[:, None]) - rebalance_band, 0.0)
                turnover = 0.5 * np.sum(changes, axis=0)
                pen += turnover_lambda * turnover
```

`current_inv` / `has_current_weights` restent nécessaires : ils servent au calcul des
frais de transaction (`current_broker_weights`) et à l'amorçage de la population.

- [ ] **Étape 4 : remplacer les appels au score**

Dans `neg_obj_batch` (l.960-963) :

```python
        base = neg_benchmark_relative_batch(
            deployed, sim_search, mean_daily, bench, alpha, downside_weight,
            annual_costs=annual_costs,
        )
```

Dans `_full_starr` (l.1267-1274) :

```python
        value = -neg_benchmark_relative(
            actual, sim_rets, mean_daily, bench, alpha, downside_weight,
            annual_cost=costs["annualized_cost_pct"],
        )
```

Dans `ticker_standalone_scores` (l.451-466), remplacer le corps du calcul final pour
retirer la division :

```python
    risk = (cvar + downside_weight * dd) * np.sqrt(252.0)
    ann = np.asarray(mean_daily, dtype=float) * 252.0
    return ann - risk
```

et adapter la docstring : le classement sert toujours à ordonner l'univers pour la
population initiale, mais sans ratio.

- [ ] **Étape 5 : injecter le portefeuille actuel dans la population**

`build_init_population` possède **déjà** un paramètre `warm_starts` (l.475) qui
insère des individus imposés dans la population, plus une copie bruitée de chacun —
aucune signature à modifier. Il suffit d'y ajouter le portefeuille détenu.

Remplacer la ligne 1124 :

```python
    warm_starts: list[np.ndarray] = [positive_seed]
```

par :

```python
    # Une seule seed (STARR_DE_MAX_SEEDS = 1) amorcee par le portefeuille REELLEMENT
    # detenu : le DE part de l'existant au lieu d'un tirage arbitraire. Le reste de
    # la population conserve la couverture de l'univers (chaque titre apparait dans
    # au moins un individu), sans quoi le DE n'aurait aucune diversite genetique.
    warm_starts: list[np.ndarray] = [positive_seed]
    if has_current_weights:
        warm_starts.insert(0, current_inv.copy())
```

- [ ] **Étape 6 : mettre à jour les tests existants impactés**

Trois fichiers référencent `neg_starr` ou le turnover et vont échouer :

- `backend/tests/test_finance/test_starr.py` — teste `neg_starr` / `neg_starr_batch`.
  Ces fonctions **restent en place** (elles ne sont plus appelées par l'optimiseur
  mais gardent leur valeur de référence) : ces tests doivent continuer à passer tels
  quels. S'ils échouent, c'est une régression involontaire.
- `backend/tests/test_finance/test_optimizer_robust.py` — appelle
  `optimize_portfolio_de`. Ajouter l'argument `benchmark_returns=` à chaque appel
  (une série de rendements aléatoires d'au moins `STARR_MIN_HISTORY_DAYS` points
  suffit) et adapter les assertions portant sur l'échelle du score.
- `backend/tests/test_finance/test_backtest.py` — vérifier la nature de la référence
  au turnover : si elle porte sur `Config.STARR_TURNOVER_PENALTY` (supprimé), retirer
  l'assertion ; si elle porte sur le turnover du backtest (module distinct), ne rien
  changer.

Ne SUPPRIMER aucun test : les adapter.

```
cd backend && uv run pytest tests/test_finance/ -v
```
Attendu : tous verts.

- [ ] **Étape 7 : commit**

```bash
git add backend/app/services/finance/buffett/optimizer.py backend/tests/
git commit -m "feat(buffett): cablage du score relatif, prior par classe, suppression du turnover"
```

---

### Task 6 : diagnostics et affichage

**Fichiers :**
- Modifier : `backend/app/services/finance/buffett/optimizer.py:1299-1359`
- Test : `backend/tests/test_finance/test_buffett_runs.py` (adapter si nécessaire)

**Interfaces :**
- Consomme : `bench` (Task 5), `asset_classes` / `prior_daily` (Task 5).
- Produit : bloc `diagnostics` en `schema_version: 3`.

- [ ] **Étape 1 : mettre à jour le bloc diagnostics**

```python
        "schema_version": 3,
        ...
        "estimation": {
            "mean_window_observations": int(len(R_mean)),
            "mean_signal_weight": float(mean_signal_weight),
            "mean_prior": "per_asset_class_median",
            "class_priors": {
                name: {
                    "n": int(sum(1 for c in ticker_classes if c == name)),
                    "annual_pct": float(
                        np.median([
                            raw_mean_daily[i] for i, c in enumerate(ticker_classes)
                            if c == name
                        ]) * 252.0 * 100.0
                    ),
                }
                for name in sorted({c for c in ticker_classes if c is not None})
            },
            "correlation_shrinkage": float(Config.STARR_CORRELATION_SHRINKAGE),
        },
        "benchmark_relative": {
            "ticker": str(Config.STARR_BENCHMARK_TICKER),
            "annual_return_pct": float(bench["annual_return"] * 100.0),
            "cvar_pct": float(bench["cvar"] * 100.0),
            "downside_deviation_pct": float(bench["downside_deviation"] * 100.0),
            "score_unit": "points de rendement annuel vs benchmark",
        },
```

Supprimer entièrement le bloc `"turnover": {...}` (l.1312-1320).

- [ ] **Étape 2 : distinguer l'échelle dans le résumé**

Le champ `resume` de `buffett_run` affiche aujourd'hui `STARR réel 2.2225`. Un score
de +3,22 points/an et un ratio de 2,22 ne sont PAS comparables : un utilisateur qui
compare deux runs côte à côte serait induit en erreur.

Dans `backend/app/services/finance/buffett/reporting.py:132`, remplacer :

```python
            f"STARR réel {float(optimized):.4f} · équipondéré {float(equal_weight):.4f}"
```

par :

```python
            f"score vs {Config.STARR_BENCHMARK_TICKER} {float(optimized):+.2f} pts "
            f"· équipondéré {float(equal_weight):+.2f}"
```

Ajouter l'import de `Config` en tête de `reporting.py` s'il est absent
(`from .config import Config`). Les décimales passent de 4 à 2 : le score est en
points de rendement annuel, la quatrième décimale n'a aucun sens.

- [ ] **Étape 3 : vérifier qu'aucune étiquette « STARR » ne subsiste à tort**

```
cd backend && grep -rn "STARR" app/ --include=*.py | grep -v "^app/services/finance/buffett/starr.py"
```
Vérifier chaque occurrence : les constantes `STARR_*` de configuration gardent leur
nom (elles pilotent toujours les mêmes mécanismes), mais tout texte affiché à
l'utilisateur qui annonce un ratio doit être corrigé.

- [ ] **Étape 4 : lancer toute la suite backend**

```
cd backend && uv run pytest -q
```
Attendu : tous verts.

- [ ] **Étape 5 : commit**

```bash
git add backend/
git commit -m "feat(buffett): diagnostics schema 3 et etiquettes du nouveau score"
```

---

## Validation finale (manuelle, après les 6 tâches)

Lancer un vrai run depuis l'application et vérifier dans les diagnostics :

1. `benchmark_relative.ticker == "CW8.PA"` avec des repères non nuls ;
2. `estimation.class_priors` montre `taux` autour de 4-5 %/an et `actions` autour de
   16-18 %/an — si `taux` ressort vers 15 %, le prior par classe n'est pas branché ;
3. le score final est **positif** (le portefeuille bat CW8.PA) ;
4. l'allocation `OBLI.PA` est très inférieure aux 96,4 % du run #50 ;
5. l'initialisation trouve un individu positif sans épuiser
   `STARR_DE_POSITIVE_INIT_MAX_BATCHES` — c'est le principal risque d'intégration :
   « positif » signifie désormais « bat CW8.PA après pénalités », nettement plus
   exigeant qu'auparavant.

Si le point 5 échoue, la piste est l'équilibre des pénalités : `CONSTRAINT_PENALTY`
(100) a été calibré contre un score de l'ordre de 1,0 et le score vaut maintenant
quelques points. C'est le seul réglage du design qui ne peut pas être justifié a
priori.

## Question restée ouverte

Le **prior sectoriel** (médiane par secteur plutôt que par classe) est tranché par un
test de persistance lancé séparément. S'il est concluant, seule la table de
correspondance passée à `class_aware_prior` change — aucune des six tâches
ci-dessus n'est à refaire.
