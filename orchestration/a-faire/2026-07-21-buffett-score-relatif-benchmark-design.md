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

**Benchmark configurable** : `Config.STARR_BENCHMARK_TICKER = "CW8.PA"`. S'il est
absent de l'univers ou sans historique suffisant, le run échoue explicitement plutôt
que de retomber silencieusement sur un benchmark nul — un score mesuré contre un
benchmark absent n'aurait aucun sens.

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

**Pas de prior sectoriel** — testé et écarté sur deux motifs mesurés :

```
   secteur (yfinance)        n     mediane H1   mediane H2
   Financial Services       79       38,40 %      23,13 %
   Technology               15       23,13 %     -12,44 %   <- 35 points d'ecart
   Consumer Defensive        1       60,63 %      16,59 %   <- "mediane" d'un titre
   persistance : Spearman 0,400  (contre une classe parfaitement stable)
```

Deux sources d'étiquettes sectorielles ont été testées, avec le **même** résultat :

- la sectorisation manuelle de ToutBroker (`Secteur 1..5`, 5 niveaux, de qualité) ne
  couvre que 12 des 136 titres vifs ayant un historique de prix ;
- les secteurs **yfinance** (colonne `Secteur`, 11 555 tickers étiquetés) ne changent
  rien : seuls **123 titres vifs** disposent de ≥ 756 j d'historique, répartis en
  groupes de 1 à 79. Les étiquettes ne sont pas le facteur limitant.

Le facteur limitant est le **crible Buffett lui-même**, et c'est voulu — entonnoir
mesuré sur les actions vives du run #50 :

```
   achat = 1                          1056
   ... liquidite >= 100k EUR/j         850   (-206)
   ... score Buffett >= 80            ~134   (-716)   <- filtre dominant, par conception
   ... >= 756 j d'historique           121
```

À noter pour qui relira ce document : une case vide dans une colonne broker de
ToutBroker.xlsx signifie **disponible**, pas indisponible (`optimizer._is_true`
l.18-22). Les 1056 actions retenues sont donc toutes accessibles ; la disponibilité
broker n'est pas un filtre limitant. Le score Buffett n'est pas persisté en base
(`buffett_run_result.poids` est `NULL`), d'où l'estimation du palier ~134 par
élimination.

L'univers d'optimisation compte ainsi ~2023 ETF pour ~123 actions. Sujet à rouvrir
uniquement si `BUFFETT_SCORE_THRESHOLD` est abaissé au point de peupler les groupes
sectoriels — ce qui est une décision d'investissement, pas technique. Le changement
serait alors local à `class_aware_prior`.

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

7. **`find_positive_random_seed`** — cherche un objectif pénalisé strictement
   positif pour amorcer le DE. Avec le nouveau score, « positif » signifie
   désormais « bat CW8.PA après pénalités », ce qui est nettement plus exigeant
   qu'auparavant. Le portefeuille équipondéré atteignant +3,22 avant pénalités, la
   condition reste atteignable, mais **le comportement de l'initialisation doit être
   vérifié sur un run réel** — c'est le principal risque d'intégration du design.

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
