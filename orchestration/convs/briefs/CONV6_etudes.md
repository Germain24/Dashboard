# CONV 6 — Module Études

## Objectif

Suivre les cours UQAM : matières du semestre, évaluations, notes, calcul GPA
semestriel et cumulatif. Lier les deadlines de devoirs au module Agenda.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. Idéal après **CONV 5 (Agenda)**
pour réutiliser le système de tâches.

## Décisions à prendre

1. **Système de notation** : UQAM utilise A+ à E avec GPA /4.3. Implémenter
   le mapping complet ?
2. **Granularité** : tracker chaque évaluation (examens, devoirs, quiz) avec
   leur pondération, ou juste la note finale du cours ?
3. **Suivi du temps d'étude** : Pomodoro / session log dès maintenant, ou V2 ?
4. **Syllabus import** : PDF + extraction IA (via CONV 12), saisie manuelle,
   ou fichier joint sans parsing ?
5. **Calcul GPA** : pondération uniforme par crédits, ou par défaut tous les
   cours = 3 crédits ?

## Fonctionnalités

### Backend (`backend/app/services/etudes/`)

- `courses.py` : modèle Cours (code, nom, semestre, crédits, prof, local)
- `evaluations.py` : modèle Évaluation (cours_id, type, ponderation, note,
  note_max, date)
- `grades.py` : calcul note pondérée par cours, GPA semestre et cumulatif
  selon barème UQAM
- `sessions.py` : log de sessions d'étude (optionnel V1)

### Endpoints

```
GET    /api/etudes/cours?semestre=
POST   /api/etudes/cours
PATCH  /api/etudes/cours/{id}

GET    /api/etudes/cours/{id}/evaluations
POST   /api/etudes/cours/{id}/evaluations
PATCH  /api/etudes/evaluations/{id}

GET    /api/etudes/gpa?semestre=&type=cumulatif|semestre
GET    /api/etudes/deadlines             # appelle CONV 5 pour les tasks liées
```

### Frontend (`frontend/app/etudes/`)

- Vue principale : cartes des cours du semestre courant avec note actuelle
- Détail cours : tableau évaluations + GPA en cours + deadlines à venir
- Vue GPA : courbe semestre par semestre, cumul
- Optionnel : timer Pomodoro avec historique

## Lien avec Agenda (CONV 5)

Quand on ajoute une évaluation avec une date future, créer automatiquement
une `Task` côté agenda avec :
- titre : `"<cours_code> - <eval_type>"`
- deadline : date de l'évaluation
- priorité : selon pondération
- lien : `course_id`

## Hors-scope

- Import automatique depuis le portail UQAM (pas d'API publique)
- Flashcards / révisions (l'agent IA CONV 12 pourra les générer à la demande)
- Calendrier de révision intelligent (V2)

## Dépendances

- Prérequis : CONV 1.
- Idéal : CONV 5 (Agenda) avant.
- Synergique : CONV 12 (agent peut interroger ce module).

## Suggestions techniques

- Barème UQAM (à vérifier) : A+=4.3, A=4.0, A-=3.7, B+=3.3, B=3.0, B-=2.7,
  C+=2.3, C=2.0, C-=1.7, D+=1.3, D=1.0, E=0.0.
- Stocker la note brute (`/100` ou `/20`) et la lettre, calculer le GPA.
- Liaison Cours ↔ Tasks Agenda via `course_id`.

## Critères de succès

- [ ] Ajout d'un cours, d'une évaluation → note moyenne pondérée correcte
- [ ] GPA semestre et cumulatif calculés correctement
- [ ] Ajouter une évaluation future crée une Task dans Agenda
- [ ] Vue GPA historique fonctionne
- [ ] L'agent peut répondre à "Combien j'ai en moyenne dans INF1000 ?" (après CONV 12)

---

## Prompt d'amorce

```
Je veux construire le module Études de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV6_etudes.md
3. (si CONV 5 faite) C:\Users\germa\Documents\GitHub\mission-control\backend\app\models\agenda.py

Pose-moi les 5 questions de "Décisions à prendre".
```
