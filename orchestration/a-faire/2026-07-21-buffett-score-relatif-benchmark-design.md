# Score relatif au benchmark + prior par classe d'actif (optimiseur Buffett) — design

**Date** : 2026-07-21 · **Statut** : approuvé

## Problème

Le run #50 (2026-07-20) alloue **96,4 % à OBLI.PA** (Amundi PEA Euro Court Terme),
un ETF monétaire qui rapporte à peine plus que l'inflation. Deux causes distinctes,
qui se cumulent.

### Cause 1 — le shrinkage vers la médiane globale

`optimizer.py:676-681` :

```
   mu[i] = 0,25 x (moyenne reelle du titre i)  +  0,75 x mediane_globale
                                                          15,79 %/an
```

Ce *shrinkage* (James-Stein) est légitime : la moyenne historique d'un titre est un
estimateur très bruité. Mesuré sur les 2145 titres du cache, première moitié de la
fenêtre contre seconde :

```
                 Pearson    Spearman
   RENDEMENT       0,001       0,266     <- ne se reproduit PAS
   RISQUE          0,003       0,935     <- se reproduit tres fortement

   top 20 % des rendements du 1er semestre -> 20,80 % sur la periode suivante
   les 80 % restants                       -> 20,51 % sur la periode suivante
```

Sans régularisation, l'optimiseur achèterait des titres dont l'avantage de rendement
s'évapore alors que leur risque, lui, persiste.

Mais le shrinkage suppose que **l'écart d'un titre à la médiane est du bruit** —
vrai entre deux actions, faux entre deux classes d'actifs. Un ETF monétaire rapporte
3,5 % parce qu'il est contractuellement conçu pour ça. Résultat :

| | rendement réel | estimation de l'optimiseur |
|---|---|---|
| OBLI.PA | **3,47 %/an** (vol 3,5 %) | `0,25×3,47 + 0,75×15,79` = **≈ 12,7 %/an** |

~9 points de rendement fictif offerts à l'obligation, sans toucher à son risque.

### Cause 2 — la forme en ratio

`STARR = rendement / risque` est **invariante d'échelle** : elle suppose
implicitement qu'on peut emprunter pour lever un actif peu risqué. Un optimiseur de
ratio charge donc structurellement le monétaire, et un CVaR proche de zéro fait
exploser le score (le plancher `max(risque, 0.005)` n'était qu'une rustine).

Preuve que corriger la cause 1 **ne suffit pas** — STARR des titres pris seuls, avec
un prior par classe déjà appliqué :

```
   OBLI.PA  0,430    <- toujours premier ex aequo
   XLP      0,430
   SPY      0,416
   CW8.PA   0,407
   SXRV.DE  0,316
```

Les deux causes doivent être traitées, pour deux raisons différentes : la forme du
score décide du classement, le prior décide si les rendements comparés sont honnêtes.

## Décision

### 1. Nouveau score, relatif au benchmark CW8.PA

```
   score = (rend_portefeuille - rend_CW8)
         - max(0 ; CVaR_portefeuille - CVaR_CW8)
         - max(0 ; DD_portefeuille   - DD_CW8)
```

Toutes les grandeurs sont annualisées et calculées sur les **mêmes scénarios
simulés** que le portefeuille. Le rendement du portefeuille reste **net des frais**
(courtage × `REBALANCES_PER_YEAR` + droits de garde) ; le benchmark, lui, est pris
brut de frais de transaction — il ne fait l'objet d'aucun arbitrage.

Trois propriétés qui découlent directement de cette forme :

- **Battre CW8.PA devient littéralement l'objectif.** Un portefeuille 100 % CW8.PA
  vaut exactement 0 avant pénalités ; tout se mesure en points de rendement/an
  gagnés contre lui.
- **Plus de division, donc plus de score infini quand le CVaR tend vers 0.** Le
  plancher `max(risque, 0.005)` disparaît, il n'a plus d'objet.
- **Être moins risqué que le benchmark ne rapporte rien** (`max(0 ; ...)`). Un actif
  à CVaR quasi nul touche 0 en bonus et garde son déficit de rendement. C'est ce qui
  élimine le biais monétaire *sans aucun seuil imposé* :

```
   ticker      rend    exc.rend  exc.CVaR  exc.DD    SCORE
   SPY       22,14 %     +5,68      2,14     0,82    +2,72
   CW8.PA    16,46 %      0,00      0,00     0,00     0,00
   BAMI.MI   54,14 %    +37,68     29,18     9,35    -0,86
   XLP        9,67 %     -6,79      0,00     0,00    -6,79
   OBLI.PA    3,24 %    -13,22      0,00     0,00   -13,22   <- de 1er a avant-dernier
```

Au niveau **portefeuille**, la diversification fait chuter le CVaR bien en dessous de
la moyenne des CVaR individuels, et le score devient franchement positif :

```
   CW8.PA (benchmark)         rend 18,28 %   CVaR 31,53 %   DD 9,24 %
   equipondere 16 lignes      rend 21,50 %   CVaR 20,75 %   DD 6,40 %   SCORE +3,22
      (moyenne des CVaR individuels 37,80 %  ->  CVaR du portefeuille 20,75 %)
   variante 70 % actions / 30 % obligations                             SCORE -3,43
```

**Unités** : le score est exprimé en **points de pourcentage annuels**, pas en
fraction. C'est ce qui garde les coefficients de pénalité existants dans le même
ordre de grandeur que le score (cf. §4).

**Benchmark configurable** : `Config.STARR_BENCHMARK_TICKER = "CW8.PA"`.

⚠️ **Le benchmark n'est PAS dans l'univers d'optimisation et ne doit pas y être.**
Vérifié sur le run #51 : CW8.PA est bien `achat=1`, liquide (3,9 M€/jour) et présent
en cache, mais il est écarté par `select_etfs_per_broker`
(855 ETF → 58, plafond `ETF_MAX_CANDIDATES_PER_BROKER = 50`) — d'où un
`named_benchmarks` vide dans les diagnostics. `deduplicate_correlated` pourrait
l'écarter de la même façon comme « jumeau d'indice ».

Ses rendements doivent donc être **injectés explicitement** :

- le runner extrait la série du benchmark **après** `returns_in_base_currency`
  (donc en EUR) et **avant** `deduplicate_tickers` / `deduplicate_correlated` /
  `select_etfs_per_broker`, qui peuvent le supprimer ;
- il la passe à `optimize_portfolio_de(..., benchmark_returns=...)` ;
- l'optimiseur l'ajoute comme **colonne supplémentaire** de la matrice envoyée à
  `simulate_regime_scenarios`, de sorte que le benchmark soit simulé *conjointement*
  avec l'univers (mêmes scénarios, mêmes dépendances de queue), puis l'exclut des
  variables de décision : `sim_rets[:, :n_inv]` pour le portefeuille,
  `sim_rets[:, n_inv]` pour le benchmark.

Le rendement espéré du benchmark passe par **le même estimateur** que les candidats
(prior par classe, classe `actions`) : comparer une estimation régularisée à une
moyenne brute biaiserait la comparaison.

Si le benchmark est introuvable ou a moins de `STARR_MIN_HISTORY_DAYS` de cours, le
run **échoue explicitement** — un score mesuré contre un benchmark absent n'aurait
aucun sens.

### 2. Prior par classe d'actif

```
   mu[i] = 0,25 x historique du titre  +  0,75 x mediane de SA CLASSE
```

Médianes observées (fenêtre 756 j, 2145 titres) et leur persistance d'un semestre à
l'autre — c'est cette stabilité qui justifie le choix de la classe comme groupe de
pairs :

```
   classe                n      mediane H1   mediane H2
   taux                270        4,32 %       5,52 %     <- stable et bas
   actions            1818       13,32 %      18,13 %
   matieres premieres   57       13,99 %      25,82 %
```

L'écart **individuel** est du bruit (Pearson 0,001) ; l'écart **entre classes** est
structurel et persiste. Le prior n'encode que cela.

**Prior sectoriel : question OUVERTE, tranchée par un test à venir.**

Un premier test a mesuré une persistance sectorielle de Spearman 0,400 seulement,
mais il était **sous-dimensionné et ne prouve rien** : il portait sur les 123 actions
de l'univers investissable, soit des groupes de 1 à 79 titres (Consumer Defensive
n'en comptait qu'un). Rien n'oblige le *prior* à être estimé sur l'univers
investissable — une action Finance au score nul reste une observation valide du
comportement du secteur Finance. Seule l'**allocation** est restreinte aux titres
éligibles.

Le pipeline actuel ne permet pas de le tester : le cache de prix
(`data/cache/price_history`) n'est alimenté que par `download_prices_bulk_with_retry`,
appelé depuis `runner.py:631` et `api/finance/buffett.py:625` avec la seule liste
éligible (`score ≥ 80` ET `achat` ET liquidité). Les ~6789 actions non éligibles
connues en base n'ont donc jamais de cours téléchargés.

**Plan retenu (décision utilisateur 2026-07-21)** :

1. Test jetable hors pipeline, sur un échantillon stratifié suffisant, pour mesurer
   la persistance sectorielle avec une vraie puissance statistique. À lancer
   **après** la fin du run en cours — un téléchargement parallèle risquerait un
   blocage Yahoo (limite à 1000 req/h depuis le 2026-07-12, à la suite d'un blocage
   sévère).
2. Si le signal sectoriel existe : les médianes sectorielles deviennent des
   **valeurs de référence persistées, recalculées ~1×/an** via une action dédiée
   (téléchargement complet, long), et non ré-estimées à chaque run. Une médiane
   sectorielle sur 5 ans ne bouge pas d'une semaine à l'autre : ce découpage
   supprime tout coût récurrent.
3. Sinon : on s'en tient au prior par classe.

**Cette question ne bloque pas l'implémentation.** Le regroupement est un paramètre
de `class_aware_prior` : passer de la classe au secteur est une substitution de la
table de correspondance, pas une réécriture. Le reste du design (score relatif,
suppression du turnover, seed unique, pénalités additives) en est indépendant.

Éléments déjà mesurés, à confirmer ou infirmer par le test :

```
   secteur (yfinance)        n     mediane H1   mediane H2
   Financial Services       79       38,40 %      23,13 %
   Technology               15       23,13 %     -12,44 %   <- 35 points d'ecart
   Consumer Defensive        1       60,63 %      16,59 %   <- "mediane" d'un titre
   persistance : Spearman 0,400  (contre une classe parfaitement stable)
```

### Source des étiquettes sectorielles

Les **étiquettes ne manquent pas** — c'est le point qui a longtemps brouillé
l'analyse :

| source | couverture |
|---|---|
| `Secteur` (yfinance), en base | **11 555 tickers**, 11 secteurs + ETF |
| `Secteur 1..5` (ToutBroker, saisie manuelle) | 12 titres vifs sur 136 en cache, mais 5 niveaux de finesse |

Ce sont les **cours** qui manquent : 6925 actions vives sont connues en base, 136
seulement ont un historique de prix, parce que seuls les titres éligibles sont
téléchargés. C'est précisément ce que le recalcul annuel viendrait combler.

Les secteurs yfinance suffiront au test et à un premier prior sectoriel ; la
sectorisation manuelle, plus fine, pourra le raffiner quand elle sera plus remplie.

### Entonnoir de l'univers investissable (contexte)

Mesuré sur les actions vives du run #50 — utile pour comprendre pourquoi l'univers
d'**allocation** compte ~2023 ETF pour ~123 actions, mais **sans rapport avec la
population d'estimation du prior** :

```
   achat = 1                          1056
   ... liquidite >= 100k EUR/j         850   (-206)
   ... score Buffett >= 80            ~134   (-716)   <- filtre dominant, par conception
   ... >= 756 j d'historique           121
```

Deux pièges pour qui relira ce document :

- une case vide dans une colonne broker de ToutBroker.xlsx signifie **disponible**,
  pas indisponible (`optimizer._is_true` l.18-22) : les 1056 actions retenues sont
  donc toutes accessibles, la disponibilité broker n'est pas un filtre limitant ;
- le score Buffett n'est pas persisté (`buffett_run_result.poids` est `NULL`), d'où
  l'estimation du palier ~134 par élimination.

Ce seuil de score est **volontaire** — c'est le crible de sélection. Il n'y a pas
lieu de l'abaisser pour peupler les groupes sectoriels : le prior s'estime sur une
population indépendante de l'éligibilité.

**Pas de taille minimale de classe.** Une classe à 1 membre dégénère en « sa propre
moyenne » — pour une obligation c'est la réponse conservatrice correcte. Un seuil
minimal ferait retomber les petites classes sur la médiane globale, c'est-à-dire
réintroduirait le bug d'origine.

### 3. Suppression de la pénalité de turnover

Doublon avéré avec les frais de transaction, qui modélisent déjà le coût en euros
des ordres (× `REBALANCES_PER_YEAR`, ~1,04 % du capital sur le run #50).
`STARR_TURNOVER_PENALTY` et `STARR_REBALANCE_BAND_PCT` sont retirés de l'objectif.

### 4. Pénalités : additives, jamais multiplicatives

Le score étant **centré sur 0 par construction**, une pénalité multiplicative
s'inverse :

```
   Portefeuille A : score -5, VIOLE la contrainte pays  ->  -5 x 0,5 = -2,5
   Portefeuille B : score -5, respecte tout             ->  -5 x 1,0 = -5,0
                                              A gagne, en trichant.

   et pire :  score 0 (le benchmark lui-meme) x n'importe quel malus = 0
              -> toutes les violations deviennent invisibles
```

Les pénalités restent donc **additives**, telles qu'aujourd'hui. Leurs coefficients
sont conservés (`CONSTRAINT_PENALTY = 100`, `STARR_CARD_BETA = 0,15`) puisque le
score est exprimé en points, mais **leur équilibre doit être vérifié
empiriquement** : c'est le seul réglage du design qui ne peut pas être justifié a
priori.

Les seuils eux-mêmes sont **inchangés** (défensif ≥ 30 %, pays ≤ 25 %,
20 lignes/broker). Décision utilisateur : il est normal qu'un ETF à 70 % US soit
pénalisé, y compris le benchmark lui-même.

### 5. Une seule seed, amorcée par le portefeuille actuel

`STARR_DE_MAX_SEEDS = 1`, et le portefeuille actuellement détenu est injecté comme
**individu de départ** dans la population initiale. Le reste de
`build_init_population` est conservé — notamment la garantie que chaque titre
apparaît dans au moins un individu. Une population réduite au seul portefeuille
actuel n'aurait aucune diversité génétique et le DE ne pourrait rien explorer.

### 6. Contrainte de rendement minimum : abandonnée

Envisagée puis écartée. Le score relatif au benchmark classe OBLI.PA avant-dernier
tout seul, et le portefeuille équipondéré rapporte déjà 21,50 % : un seuil arbitraire
à 10 % serait inopérant et fausserait l'arbitrage rendement/risque que la forme
soustractive produit naturellement.

## Changements

1. **`broker_availability.load_asset_classes()`** — calqué sur `load_etf_tickers()` :
   même source autoritaire (`ToutBroker.xlsx`, colonne `Secteur 2`), même
   mémoïsation, même invalidation par `reset_etf_cache()`. Renvoie
   `dict[ticker_MAJ → classe]` :

   | `Secteur 2` | classe |
   |---|---|
   | Obligations, **Monétaire** | `taux` |
   | Matières premières | `matieres_premieres` |
   | Actions, ou tout autre secteur non vide | `actions` |
   | vide + titre vif (`Secteur 1` ≠ ETF) | `actions` |
   | vide + ETF | absent du dict → repli médiane globale |

   La fusion Monétaire → `taux` est une décision utilisateur (2026-07-21).

   ⚠️ Le tableur contient du mojibake (`Mati�res premi�res`, `Mon�taire`) : la
   reconnaissance se fait par **préfixe désaccentué** (`oblig`, `mon`, `mati`) et non
   par égalité de chaîne, sinon Monétaire et Matières premières tombent
   silencieusement dans `actions`.

   Vérifié le 2026-07-21 : **0 ETF sans `Secteur 2`**. Le cas « classe inconnue » est
   théorique mais couvert.

2. **`optimizer.class_aware_prior(raw_mean_daily, classes)`** — fonction **pure**
   renvoyant le vecteur de prior, remplaçant le scalaire `common_mean`
   (`optimizer.py:676-681`). `classes` est une séquence de labels alignée **index par
   index** sur `raw_mean_daily` (donc sur `tickers`), `None` valant « inconnu ».

   **Population de calcul des médianes** : identique à celle du `common_mean` actuel,
   c'est-à-dire toutes les colonnes de `returns`, avant le filtre `investable` de la
   ligne 690.

3. **`starr.benchmark_relative_score(...)` + `..._batch(...)`** — remplacent
   `neg_starr` / `neg_starr_batch`. Les statistiques du benchmark (rendement, CVaR,
   DD) sont calculées **une seule fois** avant la boucle DE, sur la même matrice
   `sim_rets` que les candidats, et passées en paramètres. La version batch conserve
   l'estimation du CVaR par `np.partition` sur les `round(alpha × n_sim)` pires
   scénarios.

4. **`optimizer.optimize_portfolio_de`** — câblage : suppression du bloc turnover
   (l.730-740 et l.983-986), `STARR_DE_MAX_SEEDS` à 1, injection du portefeuille
   actuel dans la population initiale, appels au nouveau score.

5. **`Config`** — ajout de `STARR_BENCHMARK_TICKER = "CW8.PA"` ; retrait de
   `STARR_TURNOVER_PENALTY` et `STARR_REBALANCE_BAND_PCT` ; `STARR_DE_MAX_SEEDS = 1`.

6. **Diagnostics et affichage** — `schema_version` 2 → **3**.
   `estimation.mean_prior` passe à `"per_asset_class_median"`, avec le détail
   `{classe: {n, annual_pct}}`. Nouveau bloc `benchmark_relative`
   `{ticker, rend, cvar, dd, excess_return, excess_cvar, excess_dd}`. Le bloc
   `turnover` disparaît.

   ⚠️ **Le nombre affiché sous le nom « STARR » change de sens et d'échelle**
   (0,4–2,0 → −15 à +5, en points/an). Le champ `resume` de `buffett_run`, les
   `benchmarks` des diagnostics et l'affichage frontend doivent être relus : un
   « STARR 2,05 » d'un ancien run et un « score +3,22 » d'un nouveau ne sont pas
   comparables. Les runs en `schema_version: 2` gardent leur sémantique ; aucune
   migration de données n'est nécessaire (les diagnostics sont du JSON libre), mais
   l'étiquette affichée doit distinguer les deux.

7. **`find_positive_random_seed`** — le critère d'amorçage passe de « score
   strictement positif » à « **pénalité nulle** » (contraintes respectées).

   Le risque anticipé s'est matérialisé dès les tests : tant que l'objectif était
   le ratio `rendement / risque`, « positif » voulait simplement dire
   « rendement > 0 » — presque toujours vrai, donc un garde-fou quasi gratuit.
   Depuis que le score mesure l'écart au benchmark, « positif » voudrait dire
   « battre CW8.PA dès le tirage au sort » : ce serait exiger du point de départ
   qu'il résolve déjà le problème que le DE doit résoudre. Sur un univers
   synthétique à deux titres, aucun tirage n'y parvient et le run échoue.

   Le nouveau critère est celui que ce garde-fou visait réellement : l'échec
   `PositiveSeedNotFound` signale qu'aucun portefeuille aléatoire ne respecte les
   contraintes look-through — exactement le cas où l'appelant doit les relâcher.
   La relaxation automatique (défensif / pays) conserve donc tout son sens, alors
   qu'un simple « prendre le meilleur candidat » l'aurait désactivée à jamais.

   Mise en œuvre : les pénalités sont extraites de `neg_obj_batch` dans un
   `_penalties_batch` réutilisable, et `feasible_batch` expose le masque des
   candidats à pénalité nulle. `find_positive_random_seed` reçoit ce masque via un
   paramètre `feasible=`.

## Hors périmètre

Ni les copules, ni la simulation de scénarios, ni les contraintes look-through, ni la
discrétisation par broker, ni le filtre de liquidité ne sont modifiés.

## Tests

Conventions de `backend/tests/test_finance/test_constraints.py` (fonctions pures,
import dans le test, assertions numpy).

- `test_asset_classes.py` — mapping des classes, robustesse au mojibake,
  Monétaire → `taux`, titre vif sans `Secteur 2` → `actions`, ETF sans `Secteur 2` →
  absent, invalidation par `reset_etf_cache()`.
- `test_class_aware_prior.py` — une obligation à faible rendement garde une
  estimation basse ; l'ordre intra-classe est préservé ; classe singleton → sa propre
  moyenne ; classe inconnue → médiane globale.
- `test_benchmark_relative_score.py` — un portefeuille identique au benchmark score
  exactement 0 ; être **moins** risqué que le benchmark n'apporte aucun bonus ; un
  excès de risque est soustrait et non ajouté (garde-fou anti-inversion de signe) ;
  cohérence stricte entre la version scalaire et la version batch.
- Mise à jour des tests existants touchant le turnover et `neg_starr`.

## Validation finale

Un run réel doit montrer : un score final **positif** (le portefeuille bat CW8.PA),
une allocation OBLI.PA très inférieure aux 96,4 % du run #50, et une initialisation
qui trouve un individu positif sans épuiser
`STARR_DE_POSITIVE_INIT_MAX_BATCHES`.
