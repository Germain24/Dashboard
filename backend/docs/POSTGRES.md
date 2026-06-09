# Migration optionnelle vers PostgreSQL (#180)

Mission Control fonctionne sur **SQLite par défaut** mais est entièrement piloté
par `DATABASE_URL` (`app/core/config.py`). Les spécificités SQLite (WAL,
`busy_timeout`, `check_same_thread`, job de backup fichier) sont **conditionnées**
à une URL `sqlite://…` (cf. `app/core/db.py`, `app/services/scheduler/jobs/backup_db.py`),
donc rien ne bloque Postgres. Utile si tu veux accéder aux données depuis
plusieurs appareils.

## Étapes

1. **Installer le driver** (non inclus par défaut) :
   ```bash
   uv pip install "psycopg[binary]>=3.2"
   ```

2. **Pointer la base** via l'environnement (`.env` à la racine) :
   ```env
   DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/mission_control
   ```

3. **Créer le schéma** :
   ```bash
   cd backend && uv run alembic upgrade head
   ```

4. **Migrer les données existantes** (SQLite → Postgres) — via l'export/import
   intégré (#174/#175) :
   - Avec l'app encore sur SQLite : `GET /api/data/export` (ou la page **Données →
     Exporter le backup**) pour récupérer `mission-control-backup-*.json`.
   - Bascule `DATABASE_URL` vers Postgres, `alembic upgrade head`.
   - Importe le JSON : page **Données → Restaurer → Remplacer** (ou
     `POST /api/data/import` avec `{"data": <json>, "mode": "replace"}`).

## Notes

- Le **job de backup** (`backup_db`) est spécifique à SQLite : sur Postgres il
  s'ignore proprement. Utilise `/api/data/export` (JSON) ou `pg_dump` côté serveur.
- APScheduler stocke ses jobs dans la même base (`SQLAlchemyJobStore`) : ils
  sont recréés au démarrage par `register_all_jobs`, aucune migration spéciale.
- Tout le reste (modèles, requêtes) est portable : SQLModel/SQLAlchemy gère le
  dialecte automatiquement.
