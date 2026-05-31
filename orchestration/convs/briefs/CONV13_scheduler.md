# CONV 13 — Scheduler & jobs automatiques

## Objectif

Faire tourner automatiquement les tâches récurrentes : snapshot quotidien
portefeuille, génération plan nutrition matin, briefing matinal par l'agent,
analyse Buffett trimestrielle, backup SQLite, refresh météo.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée** et idéalement **CONV 12** (agent IA)
pour le briefing matinal.

## Décisions à prendre

1. **Stratégie scheduling** :
   - APScheduler dans le backend FastAPI (reco si CONV 12 faite)
   - Task Scheduler Windows externe
   - Service Python daemon séparé
2. **Jobs prioritaires V1** :
   - Snapshot portefeuille quotidien (1 fois/jour 22h)
   - Plan nutrition matin (6h30 chaque jour)
   - Briefing matinal de l'agent (7h chaque jour)
   - Refresh météo (toutes les 6h)
   - Backup SQLite (quotidien)
   - **Analyse Buffett mensuelle** (1er de chaque mois, 3h du matin —
     job *long*, plusieurs heures sur ~50k tickers à terme, à traiter avec
     `misfire_grace_time` élevé et écriture progressive en DB pour reprise
     en cas de crash)
3. **Catch-up** : si le PC est éteint au moment du run, on rattrape au démarrage ?
4. **Notifications** : où arrivent les résultats ?
   - Card "Notifications" dans le dashboard (reco V1)
   - Email
   - Push mobile (V2, stack supplémentaire)
5. **Page Jobs UI** : visualisation indispensable ou debug-only ?

## Architecture

### Backend (`backend/app/jobs/`)

```
jobs/
├── __init__.py
├── scheduler.py           # APScheduler config, jobstore SQLite
├── runner.py              # wrapper avec logging + capture erreurs
├── jobs/
│   ├── portfolio_snapshot.py
│   ├── nutrition_plan.py
│   ├── morning_briefing.py    # appelle l'agent CONV 12
│   ├── weather_refresh.py
│   ├── buffett_quarterly.py
│   ├── backup_db.py
│   └── catch_up.py
└── models.py              # JobRun (log d'exécution)
```

### Endpoints

```
GET    /api/jobs/list           # tous les jobs + prochain run + dernier
GET    /api/jobs/runs?job_id=   # historique d'exécution
POST   /api/jobs/{job_id}/run   # forcer run immédiat
POST   /api/jobs/{job_id}/pause
POST   /api/jobs/{job_id}/resume
```

### Frontend (`frontend/app/jobs/` — optionnel, ou intégré settings)

- Liste des jobs avec statut, prochain run
- Bouton "Run now" et "Pause"
- Historique des derniers runs (log + durée + statut)

## Notifications

Modèle `Notification` (timestamp, source job_id, level, message, read).
Endpoint `GET /api/notifications` et widget en haut du dashboard.

Les jobs poussent des notifs : "Plan nutrition généré", "Analyse Buffett
terminée — 3 changements suggérés", "Backup OK", etc.

## Briefing matinal

Job 7h appelle l'agent CONV 12 avec un prompt système spécial :
"Génère un briefing matinal pour Germain : agenda du jour, tenue suggérée,
plan repas, point sur la séance d'entraînement prévue, point finance, points
clés des prochains 2 jours". Résultat stocké en notification "Briefing du JJ/MM".

## Hors-scope

- Workflows complexes Airflow / Prefect (overkill).
- Notifications push mobile natives (V2).
- Triggers conditionnels complexes (V2).

## Dépendances

- Prérequis : CONV 1.
- Recommandé : CONV 12 (briefing matinal).
- Synergique : presque tous les modules (chacun peut exposer un job).

## Suggestions techniques

- APScheduler v3 avec `SQLAlchemyJobStore` pointant sur la même DB SQLite.
- Lancer le scheduler comme `@app.on_event("startup")` de FastAPI.
- Catch-up : au démarrage, rejouer les jobs `misfire_grace_time` dépassé
  seulement si flag activé sur le job.
- Backup SQLite : `sqlite3.Connection.backup()` API.

## Critères de succès

- [ ] Plan nutrition généré tout seul à 6h30 (vérifié via logs)
- [ ] Snapshot portefeuille quotidien crée bien une ligne par jour
- [ ] Briefing matinal apparaît dans les notifs à 7h
- [ ] Pause/resume d'un job fonctionne via UI
- [ ] Backup SQLite quotidien dans `data/backups/YYYY-MM-DD.db`

---

## Prompt d'amorce

```
Je veux ajouter le scheduler et les jobs automatiques à Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV13_scheduler.md

Pose-moi les 5 questions de "Décisions à prendre".
```
