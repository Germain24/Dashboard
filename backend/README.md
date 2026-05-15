# Backend — Mission Control

FastAPI + SQLModel + Alembic + SQLite, géré avec [uv](https://docs.astral.sh/uv/).

## Installation

```bash
uv sync
```

## Lancer

```bash
# Migrations
uv run alembic upgrade head
# Import legacy (depuis ../data/imports/)
uv run python scripts/import_legacy.py
# Serveur
uv run uvicorn app.main:app --reload
```

OpenAPI : http://127.0.0.1:8000/docs · Health : http://127.0.0.1:8000/health
