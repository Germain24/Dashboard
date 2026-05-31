# CONV 5 — Module Agenda (vrai)

## Objectif

Remplacer le placeholder hardcodé par un vrai agenda qui mêle :
- **Impératifs fixes** : cours UQAM, shifts barista, RDV
- **Récurrences** : cours hebdo, shifts récurrents
- **Slots libres détectés** : créneaux où caser muscu, course, cuisine
- **Tâches & deadlines** : devoirs (CONV 6 Études), courses, etc.

Le slot-finding est le différenciateur : l'agenda doit **suggérer** où placer
les activités flexibles dans les trous du calendrier.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. Idéalement avant CONV 6 (Études)
et CONV 7 (Entraînement) qui consomment l'API agenda.

## Code de référence

- `mon_espace/agenda/logic.py` — 18 lignes hardcodées, à jeter
- `mon_espace/Dashboard.py` lignes 1193-1217 — UI minimale

## Décisions à prendre

1. **Source des cours UQAM** : saisie manuelle ? import iCal du portail UQAM
   (s'il l'expose) ? Import depuis Google Calendar ?
2. **Modèle de récurrence** : RRULE iCal-style (puissant mais complexe) ou
   format simple custom (jours + heure début + heure fin) ?
3. **Suggestion de slots libres** : quel algo ?
   - Heuristique simple : trous > 1h dans la journée
   - Plus avancé : préférences horaires (muscu le matin ?), durée souhaitée,
     contraintes (pas avant 9h)
4. **Tâches** : modèle séparé ou unifié avec Event ? (Reco : séparé.)
5. **Import .ics** : V1 ou V2 ?

## Fonctionnalités

### Backend (`backend/app/services/agenda/`)

- `events.py` : CRUD événements ponctuels
- `recurrence.py` : génération d'occurrences à partir de règles
- `tasks.py` : CRUD tâches avec priorité + deadline
- `slots.py` : algo de détection de slots libres
- `ical_adapter.py` : parser .ics (V1 ou V2 selon décision)

### Endpoints

```
GET    /api/agenda/events?from=&to=     # événements dans une fenêtre
POST   /api/agenda/events
PATCH  /api/agenda/events/{id}
DELETE /api/agenda/events/{id}

GET    /api/agenda/tasks                # tâches à venir, triées
POST   /api/agenda/tasks
PATCH  /api/agenda/tasks/{id}
POST   /api/agenda/tasks/{id}/done

GET    /api/agenda/slots?date=&min_duration=&preferences=
                                         # slots libres suggérés
POST   /api/agenda/import-ical          # upload .ics
```

### Frontend (`frontend/app/agenda/`)

- Vue **Semaine** (grille type Google Cal, 7 cols × créneaux 30 min)
- Vue **Jour** (timeline horaire, slots libres mis en évidence)
- Sidebar **Tâches** triées par urgence
- Bouton **+ Ajouter** (event ou task selon contexte)
- Vue **Slots suggérés** pour caser muscu / course / cuisine

## Hors-scope

- Sync bidirectionnelle Google Calendar (V2)
- Drag-drop des événements (V2)
- Invitations / partage (single-user)

## Dépendances

- Prérequis : CONV 1.
- Consommé par : CONV 6 (Études → tâches).
- **Boucle à fermer avec CONV 7 (déjà livrée)** : afficher la séance du jour
  dans la timeline. CONV 7 expose déjà `GET /entrainement/today` qui renvoie
  `programme_jour` + slots. **Consommer via import in-process** (cf. note 14
  du PLAN.md) : `from app.services.entrainement import ...`, pas de round-trip
  HTTP. Wrap dans `try/except` avec fallback silencieux pour ne pas bloquer
  Agenda si Entraînement échoue.

## Suggestions techniques

- `python-dateutil` pour les RRULE
- `icalendar` pour le parsing .ics
- Algo slots : générer les segments occupés du jour, retourner les complémentaires
  ≥ durée min, croisés avec les préférences

## Critères de succès

- [ ] Ajouter un cours récurrent (lun-mer-ven 9h-12h) → toutes les occurrences
  visibles sur 4 semaines
- [ ] Ajouter une tâche avec deadline → apparaît triée correctement
- [ ] Requête "slots libres de ≥ 1h aujourd'hui" retourne les bons trous
- [ ] Suppression d'une occurrence récurrente ne casse pas la règle
- [ ] Vue semaine s'affiche correctement sur mobile

---

## Prompt d'amorce

```
Je veux construire le module Agenda de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV5_agenda.md

Pose-moi les 5 questions de "Décisions à prendre".
```
