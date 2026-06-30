"""API onglet Objectif (#garderobe-objectif)."""
from __future__ import annotations

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.api.garderobe import objectif as objectif_mod
from app.core.db import get_session
from app.main import create_app
from app.models.garderobe import ObjectifType, Vetement


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_get_objectif_positions_and_empty(client, session):
    session.add(ObjectifType(nom="T-shirts", ordre=0, quantite_objectif=2,
                             echelle=["Uniqlo U", "Beams Plus", "Visvim"]))
    session.add(Vetement(id="v1", nom="Tee", categorie="Haut",
                         marque="Visvim", type_objectif="T-shirts"))
    session.commit()

    r = client.get("/garderobe/objectif")
    assert r.status_code == 200
    data = r.json()
    assert data["total_emplacements"] == 2
    assert data["total_remplis"] == 1
    t = data["types"][0]
    assert t["nom"] == "T-shirts"
    assert t["emplacements"][0]["position"] == 100.0
    assert t["emplacements"][1]["statut"] == "vide"


def test_get_objectif_excess_red(client, session):
    session.add(ObjectifType(nom="Polos", ordre=0, quantite_objectif=1,
                             echelle=["Uniqlo", "Auralee"]))
    session.add(Vetement(id="p1", nom="Polo A", categorie="Haut",
                         marque="Auralee", type_objectif="Polos"))
    session.add(Vetement(id="p2", nom="Polo B", categorie="Haut",
                         marque="Uniqlo", type_objectif="Polos"))
    session.commit()

    t = client.get("/garderobe/objectif").json()["types"][0]
    assert len(t["emplacements"]) == 1
    assert len(t["excedent"]) == 1


def test_patch_vetement_type_objectif(client, session):
    session.add(Vetement(id="v9", nom="Tee", categorie="Haut"))
    session.commit()
    r = client.patch("/garderobe/vetements/v9", json={"type_objectif": "T-shirts"})
    assert r.status_code == 200
    assert r.json()["type_objectif"] == "T-shirts"


def test_post_sync(client, session, tmp_path, monkeypatch):
    p = tmp_path / "Vetements.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, "Quantité objectif", "Qualité/Prix"])
    ws.append(["T-shirts", 3, "Uniqlo U"])
    wb.save(p)
    monkeypatch.setattr(objectif_mod, "_objectif_xlsx_path", lambda: p)

    r = client.post("/garderobe/objectif/sync")
    assert r.status_code == 200
    assert r.json() == {"types": 1}
    assert session.get(ObjectifType, "T-shirts").quantite_objectif == 3


def test_post_sync_missing_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(objectif_mod, "_objectif_xlsx_path", lambda: tmp_path / "absent.xlsx")
    r = client.post("/garderobe/objectif/sync")
    assert r.status_code == 404


def test_get_objectif_non_rattaches(client, session):
    session.add(ObjectifType(nom="T-shirts", ordre=0, quantite_objectif=1,
                             echelle=["Uniqlo U"]))
    session.add(Vetement(id="ok", nom="Tee", categorie="Haut",
                         marque="Uniqlo U", type_objectif="T-shirts"))
    session.add(Vetement(id="orphan", nom="Truc", categorie="Haut",
                         marque="X", type_objectif="Inexistant"))
    session.commit()

    data = client.get("/garderobe/objectif").json()
    assert data["non_rattaches"] == 1
    assert data["non_rattaches_items"][0]["vetement_id"] == "orphan"
    assert data["non_rattaches_items"][0]["type_objectif"] == "Inexistant"
    # l'orphelin n'est compté nulle part dans les types
    assert data["total_remplis"] == 1
