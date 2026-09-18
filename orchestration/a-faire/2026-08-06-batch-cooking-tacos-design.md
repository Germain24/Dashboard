# Batch cooking tacos — design

Date : 2026-08-06
Statut : spec validée sur les 3 choix structurants, en attente de revue finale.

## Problème

Manger 2 tacos par jour, tous issus d'une **unique fournée cuisinée en début de
mois** et congelée. Les tacos couvrent une part des besoins nutritionnels ; les
courses ne financent plus que le complément. Objectif premier : **économiser**.

Trois choix ont été arrêtés avec l'utilisateur :

1. **Critère d'optimisation** : maximiser `(%macros + %micros) / prix` — le
   meilleur rapport nutrition/coût, pas une cible de couverture fixée d'avance.
2. **Une seule recette** pour tout le mois (60-62 tacos identiques).
3. **Base imposée + garniture optimisée** : la structure du taco est fixée
   (tortilla, protéine, légumes, liant), l'algorithme choisit les ingrédients et
   les grammages à l'intérieur de ce cadre.

## Ce que le catalogue permet réellement (mesuré)

Mesure faite sur les 110 aliments du catalogue, restreints aux 67 qui supportent
congélation puis réchauffage, 2 tacos/jour, poids 60 kg :

| Garniture/taco | Calories/jour | Protéines | Couverture moyenne | Micros atteints à 100 % |
|---|---|---|---|---|
| 120 g | ~55 % | ~70 % | 59 % | 27 % |
| 150 g | 64 % | 85 % | 66 % | 27 % |
| 220 g | ~75 % | ~95 % | 76 % | 36 % |

**Conséquence de conception** : viser 80 % des macros ET des micros est hors de
portée. Les micronutriments déficitaires (vitamine C, calcium, vitamine D, iode,
potassium) proviennent précisément des aliments qui supportent mal la congélation
— fruits frais, laitages, légumes crus. Le partage naturel est donc : **les tacos
portent l'énergie et les protéines, les courses portent les micronutriments.**
Aucune cible n'est codée en dur : le pourcentage réellement atteint est un
*résultat* affiché, pas un paramètre.

## Validation du principe (prototype exécuté)

Optimisation conjointe prototypée sur le vrai catalogue (150 g de garniture par
taco, 2 tacos/jour, 60 kg) :

| Macro (journée complète) | % de la cible | dont tacos |
|---|---|---|
| Calories | 101,5 % | 30,8 pts |
| Protéines | 99,4 % | 32,2 pts |
| Lipides | 98,3 % | 21,7 pts |
| Glucides | 98,9 % | 32,7 pts |

Couverture moyenne 91,4 %. Coût 1,19 $/jour de tacos + 4,41 $ de complément.

Deux enseignements. D'abord, **le surplus de macros disparaît** : la journée
complète tombe entre 98 et 101 % des cibles. Ensuite, les tacos ne portent
qu'environ **un tiers** des macros, et non les 85 % qu'atteignait le taco
optimisé isolément — c'est précisément cette place laissée libre qui permet aux
laitages, fruits et légumes frais du complément d'apporter les micronutriments
sans faire déborder l'énergie.

Le prototype ne couvrait pas encore les contraintes de structure ni la tortilla
(absente du catalogue) ; la recette définitive en différera.

## Architecture

Quatre unités, chacune testable isolément.

### 1. Données de congélation — `data/imports/Sante/tableur/aliments.csv` ✅ FAIT

Livré le 2026-08-06 (`backend/scripts/add_tortillas_congelable.py`, idempotent,
backup automatique) :

- propriété `Congelable` (1/0) — **81 aliments à 1, 31 à 0** ; les exclus tiennent
  en trois familles de texture : crus gorgés d'eau, laitages frais et fromages à
  pâte molle, fruits mangés crus. Détail et justification dans
  `README_aliments.md` ;
- **`Tortilla de mais`** (218 kcal, 5,7 g prot., 81 mg Ca, MinQty 30 g) et
  **`Tortilla de ble`** (306 kcal, 8,2 g prot., 96 µg B9, MinQty 45 g). Catalogue
  porté à **112 aliments**.

Deux réserves documentées : les teneurs des tortillas ne viennent pas de CIQUAL
(pas d'entrée fidèle) mais des étiquettes commerciales, et leurs prix sont estimés
— le scrape Super C ne remonte que des croustilles, pas de tortillas souples.

Garde-fous : `backend/tests/test_sante/test_congelable.py` (propriété présente et
binaire, les deux familles représentées, cas connus ancrés, tortillas complètes).
Sans eux, une valeur manquante deviendrait silencieusement 0 et exclurait un
aliment du batch cooking.

Ajoutés le même jour :

- propriété **`CreamiOk`** (Ninja CREAMi) — **48 aliments à 1, dont 24 sont à
  `Congelable=0`**. Voir la section « Volet CREAMi » ci-dessous ;
- **`Lait d'avoine maison`** (0,026 $/100 g contre 0,288 acheté) et **`Lait
  d'amande maison`** (0,030 contre 0,238), profils copiés sur leur équivalent
  commercial non enrichi, prix = coût réel des ingrédients. Recettes dans le
  module Cuisine (`scripts.seed_recettes_laits_vegetaux`). Catalogue à
  **114 aliments**.

Restent à ajouter si besoin : épices de base et huile de cuisson (impact
nutritionnel marginal, non bloquant pour l'optimisation).

### 1 bis. Volet CREAMi — la contrainte de congélation n'est pas unique

L'achat d'une Ninja CREAMi change une hypothèse du design. La machine rabote un
bloc congelé : l'éclatement des cellules par les cristaux de glace, qui
disqualifie fruits et laitages en plat cuisiné, y est **recherché**. Le critère
n'est donc pas le même, d'où deux propriétés distinctes plutôt qu'une.

Le recoupement est l'information utile : **24 aliments sont impropres au plat
cuisiné congelé mais parfaits en CREAMi** — fruits crus, laitages, boissons
végétales. Ce sont exactement ceux qui portent les micronutriments que les tacos
ne peuvent pas couvrir (vitamine C, calcium, vitamine D, potassium).

Conséquence : le batch cooking mensuel peut avoir **deux lots** plutôt qu'un —
les tacos (plats, `Congelable=1`) et des pots CREAMi préparés à l'avance
(`CreamiOk=1`), qui deviennent le vecteur des micros au lieu de dépendre
entièrement des courses fraîches. L'optimisation conjointe décrite plus bas
s'étend alors à trois blocs : `2·x_taco + x_creami + x_frais`, avec la même
contrainte de couverture sur la somme — donc toujours aucun surplus de macros.

Ce volet n'est **pas chiffré** : il suppose de connaître le nombre de pots CREAMi
par jour et la capacité du congélateur, qui restent à décider. Le design des
tacos ci-dessous vaut tel quel sans lui.

### 2. Optimiseur de recette — `app/services/sante/taco.py`

**Le taco et son complément sont optimisés ensemble, en une seule passe.** C'est
le point central du design. Optimiser le taco seul, puis ajouter des aliments
frais pour combler les micros, produit mécaniquement un **surplus de macros** :
un taco qui couvre déjà 85 % des protéines ne laisse plus de place calorique aux
fruits, laitages et légumes crus qui portent les micronutriments manquants — on
dépasserait alors les cibles énergétiques.

L'optimisation porte donc sur la **journée entière**, avec deux blocs de
variables :

- `x_taco` : ingrédients de la garniture, restreints à `Congelable == 1`,
  soumis aux contraintes de structure, comptés **× 2 par jour** (la recette est
  identique tous les jours du mois) ;
- `x_frais` : le complément quotidien, libre sur tout le catalogue.

La contrainte de couverture porte sur la somme `2·x_taco + x_frais`, exactement
comme l'optimisation de fenêtre actuelle. Le surplus est donc impossible par
construction : ce n'est pas une contrainte ajoutée après coup, c'est la même
cible quotidienne, simplement répartie entre deux blocs. L'objectif reste le
ratio couverture/coût, augmenté d'un léger avantage au bloc taco pour refléter
son économie réelle (achat en gros, un seul jour de cuisson).

La sortie sépare les deux blocs : `{ingrédient: grammes par taco}` d'un côté,
profil du complément quotidien de l'autre — ce dernier alimente directement la
liste de courses.

Contraintes de structure (base imposée) : exactement une tortilla ; au moins une
source protéique animale ou végétale ; au moins deux légumes ; un liant (fromage
à pâte dure, houmous ou sauce tomate). Sans elles l'optimiseur produit des
mélanges du type « 113 g de graines de courge ».

Implémentation : réutilise `ratio_optimizer.optimize_ratio`, dont le critère est
déjà exactement couverture/coût, en lui passant le vecteur de variables élargi et
les masques de blocs. Pas de second optimiseur à maintenir.

Attention grammages : les céréales et légumineuses du catalogue sont en poids
**sec**. La recette affichée doit distinguer poids sec (achat) et poids cuit
(garniture réelle), sinon un taco « 150 g » en pèse 350 g dans l'assiette.

### 3. Lot mensuel — modèle `TacoBatch` (`app/models/sante.py`)

```
mois              str    "2026-08", unique
statut            str    planifie | cuisine | epuise
recette           dict   {ingrédient: grammes par taco}
nb_tacos_cuisines int
nb_tacos_restants int
macros_par_taco   dict
micros_par_taco   dict
poids_used        float
cout_total        float
date_cuisson      date
```

Deux lots coexistent volontairement : celui du mois courant, encore en cours de
consommation, et celui du mois suivant, cuisiné avant que le premier soit fini.
Chaque lot garde ses propres macros — le lot suivant a une recette différente
(poids et promos ont changé). La consommation décrémente **toujours le lot le
plus ancien encore non épuisé** ; il passe à `epuise` en atteignant 0, et la
bascule sur le lot suivant est automatique. Un lot épuisé est conservé (il porte
l'historique nutritionnel des jours concernés).

Recalcul des macros : à la génération d'un lot, donc une fois par mois. Le poids
corporel et les promos utilisés sont figés dans le lot.

### 4. Intégration

- **Liste de courses** : les cibles de la fenêtre sont diminuées des apports des
  2 tacos du lot actif, et le panier vise le complément — c'est-à-dire exactement
  le bloc `x_frais` déjà calculé à la génération du lot. Le panier ne rachète donc
  plus ce que les tacos couvrent, et ne déborde pas non plus les macros, puisque
  les deux blocs proviennent d'une même optimisation de la journée complète. Les
  ingrédients du lot du mois suivant apparaissent, eux, dans la liste de courses
  de la fenêtre qui précède le jour de cuisson.
- **Agenda** : un événement de 3 h « Batch cooking tacos <mois suivant> » créé le
  dernier dimanche du mois, catégorie cuisine. Créé à la génération du lot, mis à
  jour et non dupliqué si le lot est régénéré.
- **UI** : une section « Tacos du mois » dans l'onglet Courses (Santé) — recette,
  macros par taco, part des besoins couverte, tacos restants, bouton « j'en ai
  mangé un ».

## Flux

```
fin de mois M-1
  └─ génération du lot M : optimisation recette → TacoBatch(statut=planifie)
     ├─ ingrédients ajoutés à la liste de courses de la fenêtre courante
     └─ événement agenda 3 h créé
  └─ jour de cuisson : statut=cuisine, nb_tacos_restants = 2 × jours du mois M
mois M
  └─ chaque jour : cibles de la fenêtre réduites de 2 tacos
  └─ consommation : décrémente le lot le plus ancien non épuisé
  └─ à 0 → statut=epuise, bascule automatique sur le lot M+1
```

## Erreurs et cas limites

- Aucun lot actif → la fenêtre fonctionne comme aujourd'hui, cibles pleines.
- Lot épuisé avant la fin du mois (tacos mangés plus vite) → les cibles
  redeviennent pleines pour les jours restants ; l'écart est visible dans l'UI.
- Optimisation impossible (catalogue trop restreint) → message explicite, aucun
  lot créé, la fenêtre reste inchangée.
- Poids corporel inconnu → même erreur 400 que la génération de fenêtre.

## Tests

- Optimiseur : la recette respecte la structure imposée ; seuls des aliments
  congelables apparaissent ; le ratio couverture/coût est meilleur que celui
  d'une recette naïve de référence.
- **Pas de surplus de macros** (test central) : sur la journée complète
  `2 tacos + complément`, calories, protéines, lipides et glucides ne dépassent
  pas les cibles au-delà de la tolérance déjà admise par l'optimiseur de fenêtre.
  Ce test doit échouer si l'on revient à une optimisation séquentielle
  (taco d'abord, complément ensuite).
- Lot : la consommation vide le lot le plus ancien d'abord ; le passage à
  `epuise` bascule sur le suivant ; un lot épuisé n'est jamais supprimé.
- Intégration courses : avec un lot actif, les cibles de la fenêtre sont bien
  réduites des apports des tacos ; sans lot, elles sont inchangées.
- Agenda : régénérer un lot ne crée pas un second événement.

## Hors périmètre (volontairement)

- Capacité du congélateur : non modélisée tant qu'elle n'est pas un problème réel.
- Plusieurs recettes par mois : écarté par l'utilisateur (une seule recette).
- Suivi de la date de congélation par taco : le lot porte une date unique.
