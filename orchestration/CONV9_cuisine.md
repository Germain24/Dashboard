# CONV 9 — Module Cuisine (recettes & meal planning)

## Objectif

Rendre la nutrition **exécutable** : recettes avec macros calculées, plan
repas hebdomadaire généré depuis les cibles nutritionnelles (CONV 3), liste
de courses auto, et pousse des dépenses vers Budget (CONV 8).

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. Idéal après **CONV 3 (Nutrition)**
pour exploiter les cibles macros.

## Décisions à prendre

1. **Source des recettes** : saisie manuelle, import depuis sites de recettes
   (parsing JSON-LD `Recipe`), ou IA qui génère depuis ingrédients (CONV 12) ?
2. **Macros recettes** : calculées depuis les ingrédients (CONV 3 aliments.csv)
   ou saisies manuellement ?
3. **Plan repas** : 1 repas / jour ou 3 repas / jour planifiés ?
4. **Liste de courses** : générée hebdo (dimanche soir auto via CONV 13),
   ou à la demande ?
5. **Inventaire frigo** : tu veux tracker ce qui est en stock pour éviter les
   recettes impossibles, ou trop de friction ?

## Fonctionnalités

### Backend (`backend/app/services/cuisine/`)

- `recipes.py` : modèle Recette (titre, portions, temps, instructions)
- `ingredients.py` : liens recette ↔ aliments + quantités
- `macros.py` : calcul auto des macros par portion depuis les aliments
- `meal_plan.py` : génération d'un plan hebdo qui couvre les cibles nutrition
- `shopping_list.py` : aggrégation des ingrédients sur la semaine,
  conversion vers une liste de courses groupée par rayon
- `inventory.py` (optionnel) : stock frigo / placard

### Endpoints

```
GET    /api/cuisine/recipes
POST   /api/cuisine/recipes
PATCH  /api/cuisine/recipes/{id}
GET    /api/cuisine/recipes/{id}/macros

POST   /api/cuisine/import-url            # parsing JSON-LD Recipe

GET    /api/cuisine/meal-plan?week=
POST   /api/cuisine/meal-plan/generate    # auto depuis cibles CONV 3
PATCH  /api/cuisine/meal-plan/{day}       # ajuster manuellement

GET    /api/cuisine/shopping-list?week=
POST   /api/cuisine/shopping-list/done    # marquer achats faits
                                          # → POST CONV 8 Budget

GET    /api/cuisine/inventory
PATCH  /api/cuisine/inventory/{ingredient_id}
```

### Frontend (`frontend/app/cuisine/`)

- Vue **Recettes** : grille de cartes, filtres (temps, macros, ingrédients)
- Détail recette : ingrédients, instructions, macros / portion, bouton "Cuisiner"
- Vue **Plan semaine** : grille 7 jours × 3 repas
- Vue **Courses** : checklist groupée par rayon, total estimé
- Vue **Inventaire** (optionnel) : ce qu'il reste

## Lien avec Nutrition (CONV 3)

Le générateur de plan repas consomme les cibles macros journalières et
choisit des recettes qui s'additionnent au plus près. Différence avec
l'optimiseur scipy actuel : on travaille sur des **plats** (combinaisons),
pas des aliments isolés.

## Lien avec Budget (CONV 8)

Marquer une liste de courses comme "achetée" pousse une transaction dans
Budget avec catégorie auto "Nourriture".

## Hors-scope

- Reconnaissance ingrédients via photo
- Recommandations basées sur l'historique (V2)
- Mode pas-à-pas en cuisine avec timers (V2)

## Dépendances

- Prérequis : CONV 1.
- Idéal : CONV 3 (Nutrition) avant.
- Synergique : CONV 8 (Budget), CONV 12 (agent peut générer recettes).

## Suggestions techniques

- Parsing recettes web : `recipe-scrapers` Python ou implémentation maison
  JSON-LD.
- Plan repas : algorithme glouton simple (chaque jour : sélectionner les
  recettes qui minimisent l'écart aux cibles).
- Liste de courses : déduplication + conversion d'unités.

## Critères de succès

- [ ] Ajouter une recette manuellement, ses macros se calculent
- [ ] Importer une recette depuis un URL marche (≥ 50 % des sites mainstream)
- [ ] Plan semaine généré couvre les cibles nutrition à ±10 %
- [ ] Liste de courses dédupe correctement les ingrédients communs
- [ ] Marquer "courses faites" crée une transaction Budget

---

## Prompt d'amorce

```
Je veux construire le module Cuisine de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV9_cuisine.md

Pose-moi les 5 questions de "Décisions à prendre".
```
