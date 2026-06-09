# Backend FastAPI — image basée sur l'image officielle uv + Python (#195).
# Contexte de build attendu : racine du repo (cf. docker-compose.yml).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Dépendances d'abord (couche cache Docker).
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Code applicatif.
COPY backend/ ./

# Base SQLite sur un volume monté (cf. compose) ; workers configurables (#200).
ENV DATABASE_URL=sqlite:////data/mission-control.db \
    WEB_CONCURRENCY=1
EXPOSE 8000
VOLUME ["/data"]

# Migrations puis serveur. WEB_CONCURRENCY=1 par défaut (état in-memory : caches
# et rate limit sont par process — voir note #200).
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1}"]
