# Mission Control — orchestration dev
# Usage : make <cible>

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
        migrate migrate-new import seed test test-backend test-frontend gen-types \
        clean fmt lint hooks

help:
	@echo "Cibles disponibles :"
	@echo "  install            -> installe backend + frontend"
	@echo "  install-backend    -> uv sync (backend)"
	@echo "  install-frontend   -> npm install (frontend)"
	@echo "  dev                -> lance backend (:8000) et frontend (:3000) en parallèle"
	@echo "  dev-backend        -> uvicorn seul"
	@echo "  dev-frontend       -> next dev seul"
	@echo "  migrate            -> applique les migrations Alembic"
	@echo "  migrate-new m=msg  -> crée une nouvelle migration auto"
	@echo "  import             -> importe les données legacy dans SQLite"
	@echo "  seed               -> charge des données de dev"
	@echo "  test               -> tests backend + frontend"
	@echo "  gen-types          -> régénère frontend/lib/types depuis l'OpenAPI"
	@echo "  fmt                -> formatte le code (ruff + prettier)"
	@echo "  lint               -> lint le code"
	@echo "  clean              -> nettoie les caches"

# ---------- INSTALL ----------
install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd frontend && npm install

# ---------- DEV ----------
dev:
	cd frontend && npx concurrently -n backend,frontend -c blue,magenta \
	  "cd ../backend && uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000" \
	  "next dev"

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev

# ---------- DB ----------
migrate:
	cd backend && uv run alembic upgrade head

migrate-new:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

import:
	cd backend && uv run python scripts/import_legacy.py

seed:
	cd backend && uv run python scripts/seed_dev.py

# ---------- TEST ----------
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -v

test-frontend:
	cd frontend && npm test --if-present

# ---------- TYPES ----------
# Génère frontend/lib/types.ts depuis l'OpenAPI, sans serveur en cours :
# on exporte le schéma depuis l'app FastAPI, puis openapi-typescript.
gen-types:
	cd backend && uv run python -c "import json; from app.main import app; open('../frontend/openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), ensure_ascii=False))"
	cd frontend && npx openapi-typescript openapi.json -o lib/types.ts

# ---------- LINT/FMT ----------
fmt:
	cd backend && uv run ruff format . || true
	cd frontend && npm run format --if-present || true

lint:
	cd backend && uv run ruff check . || true
	cd frontend && npm run lint --if-present || true

# ---------- HOOKS ----------
# Installe les hooks pre-commit (#197). Nécessite pre-commit (pipx install pre-commit).
hooks:
	pre-commit install

# ---------- CLEAN ----------
clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".next" -prune -exec rm -rf {} +
	find . -type d -name ".turbo" -prune -exec rm -rf {} +
