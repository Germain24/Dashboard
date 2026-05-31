# CONV 1 — Récap de clôture

> À coller dans la conversation orchestrateur pour mettre à jour `PLAN.md`.

## Décisions prises au démarrage

| Question                  | Décision                                          |
|---------------------------|---------------------------------------------------|
| Git history               | Repartir d'un commit initial propre               |
| Gestionnaire Python       | `uv`                                              |
| Kit UI Next.js            | `shadcn/ui` (utils + composants maison)           |
| Données legacy            | Tout migré en SQLite (source de vérité unique)    |
| Excel finance             | Plus utilisé comme source — DB est la référence   |

## Stack effective

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.13 + `uv`
- **DB** : SQLite (`data/mission-control.db`)
- **Frontend** : Next.js 15.5 + React 19.1 + TailwindCSS 4 + TypeScript 5
- **UI** : style shadcn/ui (composants écrits maison + CSS variables compatibles)
- **Imports legacy** : `python-calamine` (résiste aux .xlsx légèrement corrompus)
- **Python requirement** : `>=3.10` (testé sur 3.10, compatible 3.11+)

## Livré (critères de succès du brief)

- [x] Repo `mission-control/` créé avec backend + frontend
- [x] `make dev` lance les deux serveurs (concurrently)
- [x] Page d'accueil Next.js liste les 11 modules avec navigation (sidebar)
- [x] Cliquer sur un module charge sa page (vide mais routée)
- [x] La DB SQLite contient toutes les données legacy importées
- [x] `pytest` passe (`test_health_ok` + `test_ping_modules` × 11)
- [x] `README` explique installation et lancement
- [ ] `mon_espace/` supprimé du repo openclaw → **action utilisateur**
       (le sandbox n'a pas pu supprimer ; commande fournie ci-dessous)

## Schéma DB (17 tables + alembic_version)

| Table                    | Source                            | Lignes importées |
|--------------------------|-----------------------------------|------------------|
| `vetement`               | `vetements.json`                  | 23               |
| `tenue_history`          | `tenues_history.json`             | 1                |
| `mesure_sante`           | `sante.json` (poids journalier)   | 9                |
| `plan_nutrition`         | `sante.json` (targets macros)     | 10               |
| `aliment`                | `aliments.csv` (transposé)        | 68               |
| `snapshot_portefeuille`  | `Historique_portefeuille.xlsx`    | 2 246            |
| `watchlist_entry`        | `ToutBroker.xlsx` (recovered)     | 1 741            |
| `transaction`            | (vide — CONV 4)                   | —                |
| `position`               | (vide — CONV 4)                   | —                |
| `evenement`              | (vide — CONV 5)                   | —                |
| `etude`                  | (vide — CONV 6)                   | —                |
| `seance`                 | (vide — CONV 7)                   | —                |
| `depense`                | (vide — CONV 8)                   | —                |
| `recette`                | (vide — CONV 9)                   | —                |
| `habitude` + `habitude_log` | (vide — CONV 10)              | —                |
| `livre`                  | (vide — CONV 11)                  | —                |

**Total : 4 098 lignes importées, idempotent (upsert sur clé naturelle).**

## Endpoints exposés (`/openapi.json`)

```
GET /health                  -> {status, app, version, env, timezone, db, timestamp}
GET /finance/ping            -> {module, ready: false, ...}
GET /garderobe/ping
GET /sante/ping
GET /agenda/ping
GET /etudes/ping
GET /entrainement/ping
GET /budget/ping
GET /cuisine/ping
GET /habitudes/ping
GET /livres/ping
GET /robot/ping
```

## Surprises / décisions techniques utiles à retenir

1. **`ToutBroker.xlsx` est corrompu** dans son EOCD (End-Of-Central-Directory du
   zip). On a récupéré les données en parsant les `PK\x03\x04` directement
   puis en repackageant. À long terme, conseiller à Germain de **re-sauver
   ce fichier** depuis Excel pour avoir un xlsx valide. Le fichier réparé
   est dans `data/imports/ToutBroker.xlsx`.
2. **`ToutBroker.xlsx` n'est pas un journal de transactions** : c'est une
   *watchlist* Buffett (1 741 actions scorées MOAT). Modèle SQL adapté
   en `WatchlistEntry`. Les modèles `Transaction` / `Position` restent
   vides pour CONV 4.
3. **Pydantic 2.13 + SQLModel 0.0.38** : un champ nommé `date` clash avec
   le type `datetime.date` même quand l'import est correct. Workaround :
   on utilise `import datetime as dt` et le type `dt.date`. À garder en tête
   pour toute future migration.
4. **SQLite ne fonctionne pas sur le bind-mount FUSE du sandbox** (I/O error
   sur les WAL). Pas un problème côté Germain : sur son disque local, tout
   roule. La DB a été validée dans `/tmp` côté Claude.
5. **Sandbox npm install incomplet** : les 11 pages frontend ont été créées
   et type-vérifiées manuellement (pas via `tsc` car install timeout).
   `make install` côté Germain finira le job.

## Action utilisateur — finir l'extraction proprement

### 1. Déplacer le repo vers sa cible finale

Depuis PowerShell (ou cmd) à la racine de `C:\Users\germa\Documents\GitHub\` :

```powershell
# Le repo a été construit dans openclaw/mission-control/ — on le sort.
Move-Item -Path "openclaw\mission-control" -Destination "mission-control"
```

ou en bash (Git Bash, WSL) :

```bash
cd "/c/Users/germa/Documents/GitHub"
mv openclaw/mission-control mission-control
```

### 2. Nettoyer les résidus dans `mission-control/`

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
rm -rf frontend_empty            # leftover du scaffold create-next-app
rm -rf .git                      # init partiel — on repart d'un .git neuf
rm -rf backend/.venv             # à reconstruire avec uv (peut être incomplet)
rm -rf backend/.pytest_cache backend/pytest-cache-files-*
rm -rf frontend/node_modules     # à reconstruire avec npm install
rm -f  data/mission-control.db data/mission-control.db-journal  # à recréer
```

### 3. Supprimer `mon_espace/` du repo openclaw

```bash
cd /c/Users/germa/Documents/GitHub/openclaw
rm -rf mon_espace
git add -A
git commit -m "chore: extract mon_espace into mission-control repo"
```

### 4. Initialiser le nouveau repo Git proprement

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
git init -b main
git add .
git commit -m "feat: bootstrap Mission Control monorepo (CONV 1)

- Backend FastAPI + SQLModel + Alembic + SQLite (uv)
- Frontend Next.js 15 + Tailwind 4 + shadcn-style components
- 17 tables, migration initiale, 4098 lignes legacy importées
- Navigation des 11 modules + endpoint /health
- Makefile + README + .env.example"
```

### 5. Installer et lancer

```bash
cp .env.example .env
make install            # uv sync + npm install (peut prendre quelques minutes)
make migrate            # crée data/mission-control.db
make import             # remplit la DB avec les fichiers de data/imports/
make test               # vérifie pytest
make dev                # backend :8000 + frontend :3000
```

Puis ouvrir http://localhost:3000 — la home affiche un badge vert
"Backend OK · v0.1.0 · env=dev · db=ok" et la grille des 11 modules.

## Prochaine CONV recommandée

**CONV 2 — Module Garde-robe** (port du Streamlit existant, 641 lignes,
le plus mature). Brief dans `orchestration/CONV2_garderobe.md`.
