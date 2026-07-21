# Prior par classe d'actif + contrainte de rendement minimum (optimiseur Buffett) — design

**Date** : 2026-07-21 · **Statut** : approuvé

## Problème

Le run #50 (2026-07-20) alloue **96,4 % à OBLI.PA** (Amundi PEA Euro Court Terme),
un ETF monétaire qui rapporte à peine plus que l'inflation. Les 3,6 % restants sont
20 micro-lignes équipondérées dans le pie Trading212.

La cause n'est pas le CVaR mais **l'estimateur de rendement espéré**
(`optimizer.py:676-681`) :

```python
common_mean   = float(np.nanmedian(raw_mean_daily))      # médiane transversale
mean_daily_all = 0.25 * raw_mean_daily + 0.75 * common_mean
```

Ce *shrinkage* (James-Stein) est légitime : la moyenne historique d'un titre est un
estimateur très bruité, et sans régularisation le DE achète les gagnants du passé.
Mais il suppose que **l'écart d'un titre à la médiane est du bruit** — vrai entre
deux actions, faux entre deux classes d'actifs. Un ETF monétaire rapporte 3,5 %
parce qu'il est contractuellement conçu pour ça, pas par malchance.

Mesures sur le cache de prix (fenêtre 756 j, 2145 tickers) :

| | rendement réel | estimation de l'optimiseur |
|---|---|---|
| OBLI.PA | **3,47 %/an** (vol 3,5 %) | `0,25×3,47 + 0,75×15,79` = **≈ 12,7 %/an** |
| médiane transversale | 15,79 %/an | — |

Le shrinkage **offre ~9 points de rendement fictif** à l'obligation tout en lui
laissant son risque quasi nul : STARR standalone 1,84 contre 0,20 pour l'équipondéré.

**Corollaire décisif** : une contrainte « rendement espéré ≥ 10 % » posée sur *cet*
estimateur serait un **no-op** — le portefeuille 96 % OBLI.PA affiche déjà ~12,7 %
espéré (~11,7 % net de frais) selon le modèle. Corriger l'estimateur est donc un
préalable, pas une amélioration optionnelle.

Médianes par classe (`Secteur 2` de ToutBroker.xlsx, fenêtre 756 j) :

| classe | n | médiane |
|---|---|---|
| Actions (ETF) | 1695 | 16,72 % |
| Actions (titres vifs) | 123 | 27,27 % |
| Matières premières | 57 | 22,13 % |
| **Obligations** | 269 | **4,89 %** |
| **Monétaire** | 1 | **3,47 %** |
| *prior global actuel* | 2145 | *15,79 %* |

## Décision

1. Le shrinkage devient **conscient de la classe d'actif** : chaque titre est tiré
   vers la médiane de **sa** classe et non vers la médiane globale. Le poids de
   signal reste à 0,25. OBLI.PA passe de 12,7 % à `0,25×3,47 + 0,75×4,89` ≈ **4,5 %**.
2. Une **contrainte de rendement minimum** (10 %/an, net de frais) est ajoutée sous
   forme de **pénalité quadratique**, mécanisme identique aux contraintes existantes
   (défensif ≥ 30 %, pays ≤ 25 %).

Le shrinkage n'est **pas** supprimé : le titre garde sa personnalité, ses écarts
sont seulement divisés par 4 vers le bon groupe de pairs. L'ordre intra-classe est
préservé — le prior est un centre de gravité, jamais une valeur imposée.

**Faisabilité vérifiée** : un ETF actions monde compte ~16 % de défensif
look-through, un ETF obligataire 100 %. La contrainte « défensif ≥ 30 % » se
satisfait avec ~18 % d'obligations, soit ~14 % brut / ~13 % net de rendement
espéré. Le seuil de 10 % net mord sur les obligations sans rendre le problème
infaisable.

## Changements

1. **`broker_availability.load_asset_classes()`** — nouvelle fonction calquée sur
   `load_etf_tickers()` : même source autoritaire (`ToutBroker.xlsx`, colonne
   `Secteur 2`), même mémoïsation, même invalidation par `reset_etf_cache()`.
   Renvoie `dict[ticker_MAJ → classe]` :

   | `Secteur 2` | classe |
   |---|---|
   | Obligations, **Monétaire** | `taux` |
   | Matières premières | `matieres_premieres` |
   | Actions, ou tout autre secteur non vide | `actions` |
   | vide + titre vif (`Secteur 1` ≠ ETF) | `actions` |
   | vide + ETF | absent du dict → repli médiane globale |

   La fusion Monétaire → `taux` est une **décision utilisateur** (2026-07-21) ; elle
   règle aussi le cas dégénéré n=1.

   ⚠️ Le tableur contient du mojibake (`Mati�res premi�res`, `Mon�taire`,
   `Sant�`) : la reconnaissance se fait par **préfixe désaccentué** (`oblig`,
   `mon`, `mati`) et non par égalité de chaîne, sinon l'encodage cassé fait
   silencieusement tomber Monétaire et Matières premières dans `actions`.

   Vérifié le 2026-07-21 : **0 ETF sans `Secteur 2`** (les 124 vides du cache sont
   tous des titres vifs). Le cas « classe inconnue » est théorique mais couvert.

2. **`optimizer.class_aware_prior(raw_mean_daily, classes)`** — fonction **pure**
   renvoyant le vecteur de prior, remplaçant le scalaire `common_mean` en
   `optimizer.py:676-681`. `classes` est une séquence de labels alignée **index par
   index** sur `raw_mean_daily` (donc sur `tickers`), `None` valant « inconnu » :

   ```python
   mean_daily_all = w * raw_mean_daily + (1 - w) * prior_vec   # w = 0,25 inchangé
   ```

   **Population de calcul des médianes** : identique à celle du `common_mean`
   actuel, c'est-à-dire **toutes les colonnes de `returns`**, avant le filtre
   `investable` de la ligne 690. Le changement est strictement « une médiane → une
   médiane par classe », sans déplacement du point de calcul.

   **Pas de taille minimale de classe.** Une classe à 1 membre dégénère en « sa
   propre moyenne » — pour une obligation c'est la réponse conservatrice correcte,
   pas un bug : on perd la réduction de bruit, on ne gagne pas d'erreur. Ajouter un
   seuil ferait retomber les petites classes sur la médiane globale à 15,79 %,
   c'est-à-dire réintroduirait exactement le bug d'origine.

   Titres de classe inconnue : repli sur la médiane globale (comportement actuel).

3. **`optimizer.min_return_penalty(ann_ret, min_return, k)`** — fonction **pure**,
   branchée dans `neg_obj_batch` à côté des pénalités existantes :

   ```python
   ann_ret = (mean_daily @ W) * 252 - annual_costs[ok]        # net de frais
   pen += k * np.maximum(min_return - ann_ret, 0.0) ** 2
   ```

   Le rendement est mesuré **net des frais annualisés**, exactement la grandeur
   déjà utilisée au numérateur du STARR (`neg_starr_batch`). `ann_ret` est
   recalculé dans `neg_obj_batch` (un produit matriciel `[n_inv × S]`, négligeable
   devant le matmul `sim_rets @ W` sur `[20000 × n_inv]`) plutôt que remonté depuis
   `neg_starr_batch`, pour ne pas changer la signature d'une fonction partagée.

4. **`Config`** — deux réglages, surchargeables par `params.json` comme les autres :
   - `STARR_MIN_ANNUAL_RETURN: float = 0.10`
   - `STARR_MIN_RETURN_PENALTY: float = 1000.0`

   Ordre de grandeur visé : un manque de 10 pts coûte 10,0 et un manque de 1 pt
   coûte 0,10, à comparer à un STARR qui vaut 0,4–2,0. **Ce coefficient est le seul
   chiffre du design non justifiable a priori** : il doit être calibré sur un run
   réel et la valeur retenue rapportée. Critère de calibration : un portefeuille
   obligataire doit être classé strictement derrière un portefeuille conforme,
   sans que la pénalité écrase le signal STARR entre deux portefeuilles conformes.

5. **Diagnostics** (`optimize_portfolio_de`, bloc `diagnostics`) :
   - `schema_version` : 2 → **3**
   - `estimation.mean_prior` : `"cross_sectional_median"` → `"per_asset_class_median"`
   - `estimation.class_priors` : `{classe: {n, annual_pct}}`
   - nouveau bloc `return_constraint` : `{min_annual_return, achieved_net,
     achieved_gross, satisfied}` — c'est ce qui permet de vérifier que la
     contrainte a effectivement mordu.
   - ligne `print` récapitulative, dans le style des lignes existantes.

## Hors périmètre

Ni le CVaR, ni les copules, ni les contraintes défensif/pays, ni la discrétisation
par broker, ni le filtre de liquidité ne sont modifiés.

La pénalité de turnover (`STARR_TURNOVER_PENALTY = 0,05`) freine légèrement la
sortie des 96 % d'OBLI.PA actuellement détenus, mais elle pèse ~0,05 face à une
pénalité de rendement de l'ordre de 10 : elle ne bloquera pas la bascule.

Les runs déjà stockés en `schema_version: 2` gardent leur sémantique ; les
diagnostics sont du JSON libre, aucune migration n'est nécessaire.

## Tests

Conventions de `backend/tests/test_finance/test_constraints.py` (fonctions pures,
import dans le test, assertions numpy).

- `test_asset_classes.py` — mapping des classes, robustesse au mojibake,
  Monétaire → `taux`, titre vif sans `Secteur 2` → `actions`, ETF sans
  `Secteur 2` → absent, invalidation par `reset_etf_cache()`.
- `test_class_aware_prior.py` — une obligation à faible rendement garde une
  estimation basse ; l'ordre intra-classe est préservé ; classe singleton →
  sa propre moyenne ; classe inconnue → médiane globale.
- `test_min_return_penalty.py` — pénalité nulle si le seuil est atteint ;
  quadratique en dessous (`k·shortfall²`) ; un portefeuille obligataire est classé
  derrière un portefeuille conforme.

## Validation finale

Un run réel doit montrer, dans les diagnostics : `return_constraint.satisfied =
true`, un `achieved_net ≥ 10 %`, et une allocation OBLI.PA très inférieure aux
96,4 % du run #50.
