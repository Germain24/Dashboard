"""API des voyages confirmés : checklist + budget par étape (§5.4)."""
from __future__ import annotations

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.api.voyage import routes as voyage_routes
from app.core.db import get_session
from app.main import create_app
from app.models.voyage import LieuVoyage


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


@pytest.fixture(name="xlsx")
def xlsx_fixture(monkeypatch, tmp_path):
    """Voyage.xlsx minimal — /confirmer y écrit Visité=True."""
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Visité"])
    ws.append(["Table Mountain", False])
    wb.save(p)
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: p)
    return p


@pytest.fixture(name="lieu")
def lieu_fixture(session):
    lv = LieuVoyage(
        nom="Table Mountain", ville="Le Cap", pays="Afrique du Sud",
        aeroport_iata="CPT", jours_min=2, jours_max=4, cout_jour_estime=100.0,
        cout_hebergement_jour=60.0, cout_nourriture_jour=40.0,
        cout_activite=50.0, cout_transport_local=30.0,
    )
    session.add(lv)
    session.commit()
    session.refresh(lv)
    return lv


def _confirmer(client, lieu, **extra):
    body = {
        "lieu_ids": [lieu.id],
        "titre": "Afrique du Sud",
        "date_debut": "2026-08-01",
        "date_fin": "2026-08-15",
        "depart_iata": "YUL",
        "etapes": [{
            "lieu_id": lieu.id, "jours": 3,
            "date_arrivee": "2026-08-02", "date_depart": "2026-08-05",
        }],
        **extra,
    }
    return client.post("/voyage/confirmer", json=body)


# ── /confirmer ────────────────────────────────────────────────────────────────

def test_confirmer_sans_itineraire_reste_compatible(client, session, lieu, xlsx):
    """Ancien contrat (lieu_ids seuls) : marque visité, ne crée aucun voyage."""
    r = client.post("/voyage/confirmer", json={"lieu_ids": [lieu.id]})
    assert r.status_code == 200
    assert r.json() == {"visites": 1, "voyage_id": None}
    assert client.get("/voyage/voyages").json() == []


def test_confirmer_persiste_le_voyage(client, lieu, xlsx):
    r = _confirmer(client, lieu)
    assert r.status_code == 200, r.text
    assert r.json()["visites"] == 1
    voyage_id = r.json()["voyage_id"]
    assert voyage_id is not None

    detail = client.get(f"/voyage/voyages/{voyage_id}").json()
    assert detail["titre"] == "Afrique du Sud"
    assert detail["date_debut"] == "2026-08-01"
    assert len(detail["etapes"]) == 1
    etape = detail["etapes"][0]
    assert etape["nom"] == "Table Mountain"
    assert etape["cout_estime"] == 380.0  # 3 j * 100 + 50 + 30
    assert etape["cout_reel"] is None
    assert detail["budget"]["cout_estime_total"] == 380.0
    assert detail["budget"]["cout_projete_total"] == 380.0
    assert detail["checklist_total"] == len(detail["checklist"]) > 0
    assert detail["checklist_faits"] == 0


def test_confirmer_lieu_inconnu(client, lieu, xlsx):
    r = _confirmer(client, lieu, etapes=[{"lieu_id": 999, "jours": 2}])
    assert r.status_code == 404


def test_get_voyage_inconnu(client):
    assert client.get("/voyage/voyages/404").status_code == 404


# ── Budget par étape ──────────────────────────────────────────────────────────

def test_patch_cout_reel_et_agregation(client, lieu, xlsx):
    voyage_id = _confirmer(client, lieu).json()["voyage_id"]
    etape_id = client.get(f"/voyage/voyages/{voyage_id}").json()["etapes"][0]["id"]

    r = client.patch(
        f"/voyage/voyages/{voyage_id}/etapes/{etape_id}", json={"cout_reel": 420.0}
    )
    assert r.status_code == 200
    assert r.json()["cout_reel"] == 420.0

    budget = client.get(f"/voyage/voyages/{voyage_id}").json()["budget"]
    assert budget["cout_estime_total"] == 380.0
    assert budget["cout_reel_total"] == 420.0
    assert budget["cout_projete_total"] == 420.0
    assert budget["ecart"] == 40.0
    assert budget["etapes_avec_cout_reel"] == 1


def test_patch_cout_reel_null_efface(client, lieu, xlsx):
    voyage_id = _confirmer(client, lieu).json()["voyage_id"]
    etape_id = client.get(f"/voyage/voyages/{voyage_id}").json()["etapes"][0]["id"]
    client.patch(f"/voyage/voyages/{voyage_id}/etapes/{etape_id}", json={"cout_reel": 420.0})

    r = client.patch(f"/voyage/voyages/{voyage_id}/etapes/{etape_id}", json={"cout_reel": None})
    assert r.status_code == 200
    assert r.json()["cout_reel"] is None
    assert client.get(f"/voyage/voyages/{voyage_id}").json()["budget"]["ecart"] == 0.0


def test_patch_cout_reel_etape_inconnue(client, lieu, xlsx):
    voyage_id = _confirmer(client, lieu).json()["voyage_id"]
    r = client.patch(f"/voyage/voyages/{voyage_id}/etapes/9999", json={"cout_reel": 1.0})
    assert r.status_code == 404


# ── Checklist ─────────────────────────────────────────────────────────────────

def test_checklist_ajout_coche_suppression(client, lieu, xlsx):
    voyage_id = _confirmer(client, lieu).json()["voyage_id"]
    initial = len(client.get(f"/voyage/voyages/{voyage_id}").json()["checklist"])

    r = client.post(f"/voyage/voyages/{voyage_id}/checklist", json={"label": "Crème solaire"})
    assert r.status_code == 201
    item_id = r.json()["id"]
    assert r.json()["fait"] is False

    r = client.patch(
        f"/voyage/voyages/{voyage_id}/checklist/{item_id}", json={"fait": True}
    )
    assert r.status_code == 200
    assert r.json()["fait"] is True

    detail = client.get(f"/voyage/voyages/{voyage_id}").json()
    assert detail["checklist_total"] == initial + 1
    assert detail["checklist_faits"] == 1

    assert client.delete(f"/voyage/voyages/{voyage_id}/checklist/{item_id}").status_code == 204
    assert len(client.get(f"/voyage/voyages/{voyage_id}").json()["checklist"]) == initial


def test_checklist_item_dun_autre_voyage_est_404(client, session, lieu, xlsx):
    v1 = _confirmer(client, lieu).json()["voyage_id"]
    v2 = _confirmer(client, lieu, titre="Autre").json()["voyage_id"]
    item_id = client.get(f"/voyage/voyages/{v1}").json()["checklist"][0]["id"]

    assert client.patch(
        f"/voyage/voyages/{v2}/checklist/{item_id}", json={"fait": True}
    ).status_code == 404
    assert client.delete(f"/voyage/voyages/{v2}/checklist/{item_id}").status_code == 404


def test_checklist_voyage_inconnu(client):
    assert client.post("/voyage/voyages/404/checklist", json={"label": "X"}).status_code == 404


# ── Suppression ───────────────────────────────────────────────────────────────

def test_delete_voyage(client, lieu, xlsx):
    voyage_id = _confirmer(client, lieu).json()["voyage_id"]
    assert client.delete(f"/voyage/voyages/{voyage_id}").status_code == 204
    assert client.get("/voyage/voyages").json() == []
    assert client.delete(f"/voyage/voyages/{voyage_id}").status_code == 404


def test_list_voyages_expose_le_budget(client, lieu, xlsx):
    _confirmer(client, lieu)
    data = client.get("/voyage/voyages").json()
    assert len(data) == 1
    assert data[0]["budget"]["cout_estime_total"] == 380.0
