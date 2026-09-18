"""API /budget/import : détection de format PDF (Desjardins/Banque Populaire/
Westpac) par mot-clé, pas seulement par le fait que ce soit "un PDF" -- sinon
un relevé non-Desjardins tombait silencieusement dans le parseur Desjardins
et renvoyait 0 transaction sans erreur."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import create_app

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BP_SAMPLE = (
    _REPO_ROOT / "data" / "imports" / "Finances" / "Releve" / "Banque populaire"
    / "Compte cheque" / "2025" / "Extrait de compte - 33319172196 - 20250429.pdf"
)
_WESTPAC_SAMPLE = _REPO_ROOT / "data" / "imports" / "Finances" / "Releve" / "Westpac" / "2025-01.pdf"


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


@pytest.mark.skipif(not _BP_SAMPLE.exists(), reason="relevé réel absent (données perso non versionnées)")
def test_import_routes_banque_populaire_pdf(client):
    r = client.post(
        "/budget/import",
        files={"file": (_BP_SAMPLE.name, _BP_SAMPLE.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["format"] == "banque-populaire"
    assert data["imported"] == 7


@pytest.mark.skipif(not _WESTPAC_SAMPLE.exists(), reason="relevé réel absent (données perso non versionnées)")
def test_import_routes_westpac_pdf(client):
    r = client.post(
        "/budget/import",
        files={"file": (_WESTPAC_SAMPLE.name, _WESTPAC_SAMPLE.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["format"] == "westpac"
    assert data["imported"] > 100
