# Fenêtre nutrition batch-cook → liste de courses Super C

Statut : à faire · Créé le 2026-07-22 · **Sous-projet A** (moteur + liste à cocher)

## Contexte

Le user cuisine en **batch** : le **lundi** pour lun/mar/mer, le **jeudi** pour jeu/ven/sam/dim.
Il veut n'entrer son poids que **lundi et jeudi** et obtenir automatiquement (a) le plan
nutritionnel de la fenêtre, (b) **une** liste de courses agrégée, (c) plus tard le panier
Super C. Objectif : « manger le mieux possible pour son budget », en exploitant les promos.

Ce qui existe déjà (réutilisé, pas réécrit) :

- **Optimiseur par jour** — `backend/app/services/sante/optimizer.py::optimize_nutrition` :
  SLSQP qui choisit aliments bruts + grammes pour viser macros + ~22 micros (CIQUAL, via
  `aliments.csv`) sous contrainte de budget. Vise déjà la couverture micro et le prix.
- **Cibles + compensation J-1** — `backend/app/services/sante/targets.py::calculate_daily_targets` :
  reporte déjà le déficit/surplus de la veille sur la cible du lendemain (borné).
- **Prix Super C = Instacart** — `apply_superc_catalog_prices`
  (`backend/app/services/sante/adonis_pricing.py`) fusionne prix courants (`superc.json`) et
  circulaire/promos (`superc_flyer.json`) ; le **moins cher gagne**. Scrapers
  `frontend/.superc_scrape.mjs` / `.superc_flyer_scrape.mjs`, rafraîchis best-effort par
  `backend/app/services/cuisine/store_pricing.py::refresh_all_if_stale`.
- **Génération quotidienne** — `backend/app/services/scheduler/jobs/nutrition_plan.py` génère
  le plan du **jour** à 06:30 via `app/api/sante/plan.py::generate_plan`.

**Gap** : la génération est **par jour**, la liste de courses vient des **recettes** (pas de
l'optimiseur), il n'y a **pas de notion de fenêtre batch-cook**, et le « score » n'est ni
défini ni optimisé explicitement.

## Décisions validées avec le user (2026-07-22)

1. **Séquencement** : livrer **A** (liste à cocher) d'abord ; le **panier Instacart auto** (B)
   viendra **à la fin**, quand tout le moteur tourne.
2. **Modèle batch** : **mêmes plats sur la fenêtre, portions variables** (plus grosses les jours
   de sport). → **un seul jeu d'aliments** optimisé par fenêtre ; liste de courses = grammes
   totaux ; « combien manger » par jour = répartition.
3. **Score = couverture micro / budget, en RATIO PUR maximisé** : meilleure couverture par
   dollar, quitte à laisser tomber un micro trop cher. Les macros restent des contraintes.
4. **Report des manques = consommation RÉELLE seulement** (le user logue ce qu'il a mangé) ; un
   micro chroniquement manqué voit sa **priorité monter** jusqu'à forcer sa couverture.
5. Cadence **lun = 3 jours / jeu = 4 jours** en dur pour le v1 (configurable plus tard).

## Objectif (A)

Entrée du poids lun/jeu → **plan fenêtre** (1 jeu d'aliments) + **liste de courses agrégée à
cocher** (grammes totaux, prix + badges promo Super C) + **score** (couverture/coût) + le détail
des micros sous-couverts et leur dette. Aucune commande passée : la liste reste manuelle (B plus
tard).

---

## 1. Flux & cadence

```
Lundi  : saisie poids → fenêtre 3 jours [lun, mar, mer]
Jeudi  : saisie poids → fenêtre 4 jours [jeu, ven, sam, dim]
```

- La saisie du poids (lun/jeu) déclenche la génération de la fenêtre.
- **Filet de sécurité** : le job scheduler 06:30 auto-génère la fenêtre les lun/jeu avec le
  **dernier poids connu** si le user oublie ; il peut régénérer en entrant le vrai poids.
- Cadence lun=3 / jeu=4 en dur (v1). Les autres jours n'ont pas de saisie : ils héritent de la
  fenêtre courante.

## 2. Cibles fenêtre & score

**Cibles fenêtre = somme des cibles journalières.** Pour chaque jour de la fenêtre on calcule la
cible du jour (intensité Agenda/Entraînement conservée → un jour sport pèse davantage), puis on
**somme** : calories, protéines, lipides, glucides, les ~22 micros à atteindre, les plafonds
`*_Max`, et le budget (Budget_fenetre = Σ budgets/jour ≈ 54 CAD/3j, 72 CAD/4j).

**Macros = contraintes** (« la partie macro » conservée). **Micros = numérateur du score.**

```
Variables : x = (grammes / 100) par aliment  [convention actuelle de l'optimiseur]

Numérateur — couverture :
  C(x) = moyenne, sur les MICROS_A_ATTEINDRE, de  min( apport_m(x) / cible_fenetre_m , 1 )   (0..1)
  MICROS_A_ATTEINDRE = clés non-macro et non-"_Max" de _OPT_NUTRIENT_MAP
                       (Fibres, Magnésium, Oméga3, VitA..VitK, Calcium, Fer, Zinc,
                        Potassium, Iode, Sélénium, Phosphore) ≈ 22 micros.

Dénominateur — coût :
  P(x) = prix total = somme( x * Prix )      [Prix = Super C le moins cher courant/circulaire]

OBJECTIF :  maximiser  C(x) / P(x)

Contraintes dures :
  calories(x)  >= Calories_fenetre
  proteines(x) >= Proteines_fenetre
  P(x)         <= Budget_fenetre

Pénalités douces (conservées de l'optimiseur actuel) :
  lipides / glucides visés (moindres carrés) ; plafonds *_Max pénalisés au dépassement ;
  malus de diversité ; bornes par aliment (MaxQty ; MinQty en semi-continu + snap post-SLSQP).

Affichage (métriques) :
  - couverture_moyenne = C(x*)                       (0..100 %)
  - pct_micros_atteints = # micros avec apport>=cible / total   (0..100 %)
  - cout_total = P(x*)   ;   score_affiche = C(x*) / P(x*)
```

**Implémentation du ratio (recommandée) — itération de Dinkelbach** autour du SLSQP existant :

```
t_0 = 0
répéter :
  x* = argmax [ C(x) - t_k * P(x) ]  sous les contraintes dures   # = 1 appel optimize_nutrition
  t_{k+1} = C(x*) / P(x*)
jusqu'à  |C(x*) - t_k * P(x*)| < eps   (convergence, ~3–6 itérations ; nb d'itérations borné)
```

Chaque sous-problème est **l'optimiseur actuel avec le poids-prix = t_k** → on réutilise
`optimize_nutrition` tel quel (le terme prix passe d'un mini 0.001 fixe à `t_k` piloté par
Dinkelbach). **Repli** si jugé trop lourd au 1er jet : passe unique = objectif actuel avec un
poids-prix fortement relevé (comportement « bang-for-buck » approché, sans garantie d'optimalité
exacte du ratio).

**Répartition par jour** : le jeu d'aliments (grammes **totaux**) est découpé par jour au
**prorata des calories-cibles du jour** :
```
portion_jour_i = grammes_totaux * ( Calories_cible_i / Σ Calories_cible )
```
→ mêmes plats, portion plus grosse les jours de sport. Conséquence assumée : le **ratio des
macros est ~constant d'un jour à l'autre** (on ne fait varier que la quantité), cohérent avec
« mêmes plats, portions variables ». La liste de courses reste la **somme** (inchangée par la
répartition).

## 3. Report à priorité croissante (basé conso réelle)

Le user **logue ce qu'il a réellement mangé** par jour (`consumed`, mécanisme existant, via
/score ou `PATCH /sante/plan/{date}`). À la génération de la fenêtre suivante :

```
Pour chaque nutriment n, sur la fenêtre PRÉCÉDENTE :
  conso_reelle_n = Σ (sur ses jours)  consumed[n]
  cible_n        = Σ (sur ses jours)  targets[n]
  ecart_n        = cible_n - conso_reelle_n

Déficit (ecart_n > 0, micro à atteindre) :
  - cible_fenetre_n += min(ecart_n, plafond_report)        # dette reportée, bornée
  - serie_n += 1                                            # compteur de dette consécutive
  - poids_n = poids_base_n * (ESCALADE ** serie_n)  plafonné à POIDS_MAX
      → plus la dette dure, plus le micro est prioritaire, jusqu'à FORCER sa couverture
        malgré le coût (contrepoids du ratio pur).

Surplus (ecart_n < 0) :
  - serie_n = 0
  - crédit borné reporté (réduction bornée de la cible, cf. _safe_compensated_target existant),
    avec un plafond de crédit ~nul pour les vitamines hydrosolubles (un excès de VitC ne se
    « banque » pas).
```

`serie_n` (dette par micro) est **persistée** sur l'état de la fenêtre (cf. §5). On **étend**
`calculate_daily_targets` (déjà responsable de la compensation J-1) en une variante **fenêtre +
série de dette**, plutôt que d'ajouter un mécanisme parallèle.

## 4. Prix Super C live + promos

- À la génération (lun/jeu), **rafraîchir les caches Super C** (`superc.json` +
  `superc_flyer.json`) s'ils sont périmés, en réutilisant `store_pricing.refresh_if_stale` /
  `refresh_all_if_stale`. Idéal le **jeudi**, jour où la circulaire QC bascule. **Best-effort** :
  scrape en échec → on garde le cache, la génération n'est jamais bloquée.
- L'optimiseur voit déjà le **moins cher entre prix courant et circulaire** par aliment
  (`apply_superc_catalog_prices`) → il exploite les promos pour **gonfler le score** (prix plus
  bas ⇒ dénominateur plus petit ⇒ ratio plus haut).

## 5. Modèle de données & UX

**Données**

- On conserve **une ligne `PlanNutrition` par jour** de la fenêtre : `date`, `poids_used`,
  `intensite`, `targets` (jour), `quantites` (= **portion du jour**), `totals`, `consumed`
  (loggé). Nécessaire au report « conso réelle » et à la page /score.
- Nouvelle table légère **`WindowPlan`** (recommandé plutôt que tout empiler dans `extra`) portée
  par le jour-ancre :
  ```
  WindowPlan :
    anchor_date (lun|jeu), length (3|4), jours[list date]
    poids_used
    food_set     : {aliment: grammes_totaux}      # = base de la liste de courses
    shopping_list: [ {aliment, quantite_totale, prix_superc, promo(bool)} ... ]
    score        : {couverture_moyenne, pct_micros_atteints, cout_total, ratio}
    debt_series  : {micro: serie}                  # dette pour l'escalade §3
    warning      : str | null
  ```

**UX** — page Santé, carte **« Fenêtre »** :

- Saisie du poids (lun/jeu) → bouton **« Générer la fenêtre »**.
- **Plan par jour** : tableau jour × aliments (portions).
- **Liste de courses à cocher** : `aliment | quantité totale | prix Super C | badge promo`.
- **Bloc Score** : couverture %, coût total, ratio ; **liste des micros sous-couverts + leur
  dette** (transparence sur ce que le ratio « abandonne » temporairement).
- Bouton **« Régénérer »** (seed aléatoire, comme aujourd'hui).

**Endpoints** (extension de `backend/app/api/sante/plan.py`) :

```
POST /sante/fenetre/generate  {anchor_date?, poids?, force?}  -> WindowPlanResponse
GET  /sante/fenetre/current                                   -> WindowPlanResponse
# log conso : PATCH /sante/plan/{date} existant, inchangé
```

**Scheduler** : `jobs/nutrition_plan.py` détecte lun/jeu et génère la **fenêtre** (au lieu du
seul jour). Les autres jours : no-op (la fenêtre courante couvre déjà le jour).

## 6. Découpage & séquencement

- **A (cette spec)** : moteur fenêtre + score ratio + report escaladé + liste de courses agrégée
  à cocher + UX + scheduler. **Utile seul** (liste imprimable/cochable).
- **B (plus tard)** : panier **Instacart** auto (login, matching aliment→produit Super C,
  add-to-cart). Dépend de A. Spec + plan dédiés le moment venu.

## Hors scope (v1)

- Panier Instacart auto (= B).
- Toute source de prix hors Super C.
- Refonte de la liste de courses issue des **recettes** (`cuisine/shopping_list.py`) : la liste
  « fenêtre » vient de l'**optimiseur**, elle ne remplace pas encore le flux recettes.
- Cadence configurable, semaines à jours fériés / décalés.

## Critères d'acceptation / tests

1. **Cibles fenêtre** = somme exacte des cibles journalières (macros, micros, plafonds, budget).
2. **Répartition** : Σ des portions/jour = grammes totaux ; portion_i ∝ Calories_cible_i.
3. **Score** : sur catalogue factice, `C/P` calculé = valeur attendue ; `pct_micros_atteints`
   correct.
4. **Ratio (Dinkelbach)** : converge (borné) ; à budget large, atteint la couverture pleine au
   **coût minimal** ; à budget serré, privilégie le **meilleur ratio** (laisse des micros chers).
5. **Report/escalade** : un micro sous-consommé N fenêtres d'affilée voit son poids escalader et
   **finit couvert** ; un surplus remet la série à 0 ; crédit VitC hydrosoluble ~nul.
6. **Promos** : circulaire moins chère que le prix courant → gagne, `promo=True`, et **améliore
   le score**.
7. **Best-effort scrape** : caches absents / scrape en échec → génération non bloquée, prix de
   repli utilisés.
8. **Persistance** : `WindowPlan` + `PlanNutrition`/jour cohérents ; `consumed` reste par jour et
   alimente le report.

## Risques assumés

- **Ratio pur** ⇒ micros chers (Oméga-3, VitD) possiblement non couverts tant que la dette n'a
  pas escaladé. Contrepoids = report/escalade §3. **Accepté** (choix user).
- **Conso réelle seulement** ⇒ si le user ne logue pas, aucune dette n'est détectée (report nul).
  **Accepté** (choix user).
- **Dinkelbach** ajoute des itérations SLSQP (perf) → nb d'itérations borné + repli mono-passe.
- **Prorata calories** ⇒ ratio macro ~constant/jour (approximation). **Accepté** (mêmes plats).
