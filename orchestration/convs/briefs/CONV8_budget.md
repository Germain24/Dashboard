# CONV 8 — Module Budget (dépenses personnelles)

## Objectif

Suivre les dépenses quotidiennes pour comprendre où part l'argent : loyer,
courses, sorties, abonnements, transport. **Distinct de Finance** (qui gère
l'investissement long terme). Le budget permet de savoir combien il reste à
épargner / investir chaque mois.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**.

## Décisions à prendre

1. **Source des transactions** : import CSV banque (Desjardins, RBC, etc.),
   saisie manuelle, ou les deux ?
2. **Catégorisation** : règles auto basées sur mots-clés (`STARBUCKS → Café`),
   ou tagging manuel post-import ?
3. **Périodicité budget** : mensuel uniquement, ou aussi annuel (assurances,
   etc.) ?
4. **Devise** : CAD uniquement, ou multi-devise avec conversion ?
5. **Lien Cuisine/Nutrition** : tu veux que le module Cuisine (CONV 9)
   pousse les courses dans Budget catégorie "Nourriture" automatiquement ?

## Fonctionnalités

### Backend (`backend/app/services/budget/`)

- `transactions.py` : modèle Transaction (date, montant, marchand,
  catégorie, compte, devise)
- `categories.py` : hiérarchie catégories (Logement > Loyer, Charges...)
- `rules.py` : règles de catégorisation auto (regex sur marchand)
- `budgets.py` : enveloppe budgétaire par catégorie par mois
- `imports.py` : parsing CSV banque (formats courants Desjardins / RBC)

### Endpoints

```
GET    /api/budget/transactions?from=&to=&category=
POST   /api/budget/transactions           # saisie manuelle
PATCH  /api/budget/transactions/{id}      # re-catégoriser
POST   /api/budget/import                 # upload CSV

GET    /api/budget/categories
POST   /api/budget/categories

GET    /api/budget/rules
POST   /api/budget/rules                  # créer règle "STARBUCKS → Café"
POST   /api/budget/rules/apply            # ré-appliquer à tout l'historique

GET    /api/budget/envelopes?month=       # budget par catégorie
POST   /api/budget/envelopes              # définir budget mensuel

GET    /api/budget/summary?month=         # entrées, sorties, par catégorie
GET    /api/budget/cashflow?from=&to=     # série temporelle
GET    /api/budget/disposable             # combien reste à investir/épargner
```

### Frontend (`frontend/app/budget/`)

- Vue **Mois en cours** : entrées, sorties, solde, top catégories
- Vue **Transactions** : liste filtrable, ré-catégorisation rapide
- Vue **Catégories** : pie / bar des dépenses par catégorie
- Vue **Budget** : enveloppes mensuelles vs réel (rouge si dépassé)
- Vue **Tendances** : 6/12 derniers mois

## Hors-scope

- Synchronisation bancaire automatique (Plaid, Salt Edge — payant, complexe).
- Multi-utilisateurs / partage.
- Investissements : reste dans Finance (CONV 4).

## Dépendances

- Prérequis : CONV 1.
- Synergique : CONV 9 (Cuisine peut pousser les courses), CONV 4 (Finance
  peut lire le "disposable" pour suggérer un montant à investir).

## Suggestions techniques

- Format pivot transaction : `date, account, description, amount, currency, category`.
- Règles : ordre de priorité, mots-clés multiples possibles, dernière modification.
- Caching agressif des vues mensuelles (peu de churn).

## Critères de succès

- [ ] Import d'un CSV banque catégorise ≥ 70 % des transactions auto via règles
- [ ] Budget mensuel "Nourriture: 400 CAD" → vue qui montre 234/400, OK vert
- [ ] Disposable mensuel calculé correctement (revenus - dépenses)
- [ ] Tendance 12 mois affichée par catégorie

---

## Prompt d'amorce

```
Je veux construire le module Budget de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV8_budget.md

Pose-moi les 5 questions de "Décisions à prendre".
```
