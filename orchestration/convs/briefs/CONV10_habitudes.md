# CONV 10 — Module Habitudes (habit tracker)

## Objectif

Tracker quotidien des habitudes binaires ou quantifiables : "j'ai fait ma
muscu", "j'ai lu 30 min", "j'ai médité", "j'ai dormi ≥ 7h", "pas de junk
food". Avec compteur de streak (jours consécutifs), heatmap annuelle, et
synergies avec les autres modules (auto-cocher quand une séance entraînement
est loggée, par exemple).

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**.

## Décisions à prendre

1. **Liste initiale d'habitudes** : laquelle ? Je propose un set de départ :
   - Muscu
   - Course à pied
   - Lecture 30 min
   - Sommeil ≥ 7h
   - Pas de junk food
   - Pas de mobile au lit
2. **Habitudes binaires uniquement, ou aussi quantifiables** ?
   (binaire = oui/non, quantifiable = "30 min lecture", "2 L d'eau")
3. **Auto-coche depuis autres modules** : si CONV 7 enregistre une séance,
   cocher auto "Muscu" ? (Recommandé.)
4. **Fréquence** : toutes les habitudes daily, ou support de "3× par semaine" ?
5. **Pénalité de rupture** : streak repart à zéro après 1 oubli, ou tolérance
   1 jour ?

## Fonctionnalités

### Backend (`backend/app/services/habitudes/`)

- `habits.py` : modèle Habit (nom, type binaire|quantifiable, cible,
  fréquence, source auto facultative)
- `entries.py` : modèle HabitEntry (habit_id, date, valeur, auto)
- `streaks.py` : calcul streak courant + record
- `heatmap.py` : matrice 53 sem × 7 jours pour visualisation type GitHub

### Endpoints

```
GET    /api/habitudes/habits
POST   /api/habitudes/habits
PATCH  /api/habitudes/habits/{id}
DELETE /api/habitudes/habits/{id}

GET    /api/habitudes/today              # checklist du jour
POST   /api/habitudes/entries            # cocher une habitude
PATCH  /api/habitudes/entries/{id}

GET    /api/habitudes/streaks
GET    /api/habitudes/heatmap?habit_id=&year=
GET    /api/habitudes/stats              # taux complétion par habitude
```

### Frontend (`frontend/app/habitudes/`)

- Vue **Aujourd'hui** : checklist verticale, chaque habitude avec son streak
- Vue **Heatmap** : matrice annuelle façon GitHub par habitude
- Vue **Stats** : taux de complétion, comparaison entre habitudes
- Bouton **+ Habitude** modal

## Auto-cochage (hooks)

Quand une autre conv déclenche un événement métier, l'habitude liée se coche :
- CONV 7 `POST /entrainement/sessions` (≥ 1 série) → habit "Muscu" cochée
- CONV 7 `POST /entrainement/cardio` (course) → habit "Course" cochée
- CONV 11 `POST /livres/sessions` (≥ 30 min) → habit "Lecture" cochée

Implémentation : pub/sub interne ou simples appels directs entre services.

## Hors-scope

- Notifications push de rappel (CONV 13 si voulu)
- Gamification poussée (badges, etc.)
- Partage social (single-user)

## Dépendances

- Prérequis : CONV 1.
- Synergique : CONV 7, CONV 11 (auto-cochage).

## Suggestions techniques

- Stocker l'entrée du jour `(habit_id, date)` unique → upsert simple.
- Heatmap : précalculer côté backend, cacher 1h.
- Streak : calcul on-the-fly sur les 365 derniers jours.

## Critères de succès

- [ ] Créer 6 habitudes initiales, cocher 5 d'affilée → streak = 5
- [ ] Logger une séance muscu coche automatiquement "Muscu"
- [ ] Heatmap annuelle affichée correctement avec dégradé de couleurs
- [ ] Mobile-friendly (la vue du jour doit être tappable rapidement)

---

## Prompt d'amorce

```
Je veux construire le module Habitudes de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV10_habitudes.md

Pose-moi les 5 questions de "Décisions à prendre".
```
