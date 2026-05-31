# CONV 7 — Module Entraînement (sport, prise de muscle)

## Objectif

Module dédié à l'entraînement physique : programmation muscu + cardio, log
de séances (séries × reps × poids), progression sur les mouvements clés,
estimation 1RM, planification dans l'agenda. **Critique** pour soutenir
l'objectif de prise de muscle (lien direct avec CONV 3 Nutrition).

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. Idéal avant CONV 3 (Nutrition)
pour que les macros s'ajustent à la charge réelle.

## Décisions à prendre

1. **Type d'entraînement principal** : push/pull/legs ? upper/lower ?
   full body 3×/sem ? autre split ?
2. **Cardio** : course à pied uniquement, ou aussi vélo / autres ? Tracking
   distance + temps + FC moyenne ?
3. **Catalogue d'exercices** : import depuis une base ouverte (wger,
   exrx.net) ou saisie progressive au fur et à mesure ?
4. **1RM** : estimation Epley `1RM = poids × (1 + reps/30)`, ou formule au choix
   (Brzycki, Lombardi) ?
5. **Photos progression** : intégrer au module ou laisser dans CONV 3 Santé ?

## Fonctionnalités

### Backend (`backend/app/services/entrainement/`)

- `exercises.py` : catalogue exercices (nom, muscles cibles, type)
- `programs.py` : programme d'entraînement hebdomadaire
- `sessions.py` : log d'une séance (date, exercices, séries)
- `sets.py` : modèle Série (exercice_id, reps, poids, RPE optionnel)
- `progression.py` : progression sur un exercice (volume, intensité, 1RM
  estimé), tendance 4 semaines
- `cardio.py` : log course à pied / autres (distance, temps, FC, pace)

### Endpoints

```
GET    /api/entrainement/exercises
POST   /api/entrainement/exercises          # ajout exercice perso

GET    /api/entrainement/program            # programme courant
POST   /api/entrainement/program            # créer / éditer

GET    /api/entrainement/sessions?from=&to=
POST   /api/entrainement/sessions           # logger une séance
GET    /api/entrainement/sessions/{id}

GET    /api/entrainement/progression/{exercise_id}
                                            # courbe sur un mouvement
GET    /api/entrainement/1rm/{exercise_id}  # 1RM estimé courant

GET    /api/entrainement/cardio?from=&to=
POST   /api/entrainement/cardio

GET    /api/entrainement/intensity/today    # consommé par CONV 3 Nutrition
                                            # : low / medium / high / none
```

### Frontend (`frontend/app/entrainement/`)

- Vue **Aujourd'hui** : séance du programme du jour, log live des séries
- Vue **Programme** : édition du split hebdo
- Vue **Progression** : courbes 1RM + volume par mouvement clé
- Vue **Cardio** : log course, distance cumulée, allure moyenne
- Vue **Calendrier** : sessions des 30 derniers jours

## Lien avec Nutrition (CONV 3) — contrat figé

CONV 3 a livré un placeholder `default_intensity_for_date(date)` qui retourne
`medium` les lundi/mardi/mercredi/vendredi/samedi et `none` sinon. CONV 7
remplace ce placeholder.

**Contrat à respecter strictement** (pour ne rien casser dans Santé) :

- Nouvel endpoint : `GET /api/entrainement/intensity/{date}` (format
  `YYYY-MM-DD`).
- Retour : `{"date": "YYYY-MM-DD", "intensity": "none" | "low" | "medium" |
  "high"}`.
- Sémantique :
  - `none` : pas de séance prévue ce jour
  - `low` : récup active / mobilité (< 30 min, faible charge)
  - `medium` : séance normale (~ 45-60 min)
  - `high` : séance lourde (> 60 min OU charge > 80 % du 1RM moyen)

Côté Santé, la seule modification sera dans `routes_sante.py` (remplacer
l'appel à `default_intensity_for_date()` par un appel au nouvel endpoint).
**Ne pas toucher** à `services/sante/intensity.py` ni à `intensity_modifiers()`
— le mapping `intensity → (activity_factor, surplus_kcal, protein_per_kg,
lipid_per_kg)` reste figé côté Santé.

Conserver `default_intensity_for_date()` comme fallback si Entraînement est
indisponible ou si aucune séance n'est planifiée pour la date demandée.

## Lien avec Agenda (CONV 5)

`POST /api/entrainement/sessions` peut créer un événement Agenda lié.
Inversement, l'algo "slots libres" suggère où placer les séances du programme.

## Hors-scope

- Import depuis montre connectée (Garmin, Apple Watch) — V2
- Coach IA suggérant des programmes (l'agent CONV 12 pourra le faire)
- Vidéos d'exécution

## Dépendances

- Prérequis : CONV 1.
- Idéal : CONV 5 (Agenda) avant pour l'intégration calendaire.
- Consommé par : CONV 3 (Nutrition) pour intensité.

## Suggestions techniques

- Catalogue de départ : importer un sous-set de wger (open data, JSON).
- 1RM Epley simple, exposer le calcul en service partagé.
- Pour le log live de séance : Optimistic UI côté Next.js (afficher la série
  avant que le POST revienne).

## Critères de succès

- [ ] Logger une séance complète (5 exos × 4 séries) en moins de 2 min
- [ ] Voir la courbe 1RM estimée du squat sur 90 jours
- [ ] Course du jour loggée avec distance + temps + pace
- [ ] CONV 3 Nutrition appelle bien `/intensity/today` et ajuste les macros
- [ ] Agenda affiche la séance du jour dans la timeline

---

## Prompt d'amorce

```
Je veux construire le module Entraînement de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV7_entrainement.md

Pose-moi les 5 questions de "Décisions à prendre".
```
