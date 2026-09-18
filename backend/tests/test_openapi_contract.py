"""Test de contrat OpenAPI (#187).

Garde-fou : le schéma OpenAPI se génère et expose les endpoints dont le
frontend dépend. Une route renommée/supprimée par mégarde casse ce test avant
de casser le front (les types TS sont générés depuis ce schéma — cf. #17).
"""

from app.core.config import settings
from app.main import app

# Endpoints clés consommés par le frontend (sans préfixe).
EXPECTED = [
    "/health",
    "/finance/state",
    "/budget/by-category",
    "/habitudes/today",
    "/livres/books",
    "/agenda/today",
    "/jobs/list",
    "/notifications",
    "/notifications/prefs",
    "/data/export",
    "/data/import",
]


def test_openapi_generates():
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert "paths" in schema and len(schema["paths"]) > 50


def test_openapi_exposes_frontend_endpoints():
    paths = set(app.openapi()["paths"].keys())
    prefix = settings.api_v1_prefix
    missing = [e for e in EXPECTED if e not in paths and f"{prefix}{e}" not in paths]
    assert not missing, f"Endpoints attendus absents de l'OpenAPI : {missing}"


def test_openapi_components_present():
    schema = app.openapi()
    # Au moins quelques schémas de modèles exposés (contrat de types front/back).
    assert "components" in schema
    assert schema["components"].get("schemas")
