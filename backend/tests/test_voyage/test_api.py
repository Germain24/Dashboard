"""API Voyage : sync, lieux, planifier, confirmer."""
from __future__ import annotations

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.api.voyage import routes as voyage_routes
from app.core.config import settings
from app.core.db import get_session
from app.main import create_app
from app.models.voyage import LieuVoyage


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


def test_post_sync(client, monkeypatch, tmp_path):
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre",
               "Aéroport (IATA)", "Jours min", "Jours max", "Coût/jour estimé"])
    ws.append(["Table Mountain", "Le Cap", "Afrique du Sud", False, 1, "CPT", 2, 4, 80])
    wb.save(p)
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: p)

    r = client.post("/voyage/sync")
    assert r.status_code == 200
    assert r.json() == {"lieux": 1, "incomplets": []}


def test_post_sync_missing_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: tmp_path / "absent.xlsx")
    r = client.post("/voyage/sync")
    assert r.status_code == 404


def test_get_lieux(client, session):
    session.add(LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=4,
                            cout_jour_estime=80.0))
    session.add(LieuVoyage(nom="K-2"))  # incomplet
    session.commit()

    r = client.get("/voyage/lieux")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    par_nom = {d["nom"]: d for d in data}
    assert par_nom["Table Mountain"]["complet"] is True
    assert par_nom["K-2"]["complet"] is False


def test_get_lieux_incomplet_sans_cout_jour_estime(client, session):
    """Issue 3 (revue finale) : aéroport + jours renseignés mais coût/jour
    manquant -> pas utilisable comme candidat (sinon traité comme gratuit)."""
    session.add(LieuVoyage(nom="Sans coût", aeroport_iata="CPT", jours_min=2, jours_max=4,
                            cout_jour_estime=None))
    session.commit()

    r = client.get("/voyage/lieux")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["complet"] is False


def test_planifier_rejects_more_than_25_candidats(client, session):
    ids = []
    for i in range(26):
        lv = LieuVoyage(nom=f"L{i}", aeroport_iata="XXX", jours_min=1, jours_max=1, cout_jour_estime=10.0)
        session.add(lv)
        session.commit()
        session.refresh(lv)
        ids.append(lv.id)

    r = client.post("/voyage/planifier", json={
        "candidats": ids, "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400


def test_planifier_rejects_incomplete_lieu(client, session):
    lv = LieuVoyage(nom="Incomplet")  # pas d'aéroport/jours
    session.add(lv)
    session.commit()
    session.refresh(lv)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400
    assert "Incomplet" in r.json()["detail"]


def test_planifier_rejects_lieu_sans_cout_jour_estime(client, session):
    """Issue 3 (revue finale) : sans coût/jour, un lieu ne doit pas passer pour
    « complet » et se retrouver traité comme gratuit par le solveur."""
    lv = LieuVoyage(nom="Sans coût", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=None)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400
    assert "Sans coût" in r.json()["detail"]


def test_planifier_happy_path(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "EUR", "duree_min": 600},
    )

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["etapes"]) == 1
    assert data["etapes"][0]["lieu_id"] == lv.id
    assert data["etapes"][0]["jours"] == 2
    assert data["cout_transport"] == 1000.0  # aller + retour à 500 chacun
    assert data["cout_sejour"] == 160.0  # 2 jours x 80
    assert data["cout_total"] == 1160.0


def test_planifier_includes_coordinates(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "EUR", "duree_min": 600},
    )
    monkeypatch.setattr(
        voyage_routes, "lookup_coords",
        lambda iata, **kwargs: {"YUL": (45.4706, -73.7408), "CPT": (-33.9648, 18.6017)}.get(iata),
    )

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["depart"] == {"iata": "YUL", "lat": 45.4706, "lon": -73.7408}
    assert data["arrivee"] == {"iata": "YUL", "lat": 45.4706, "lon": -73.7408}
    assert data["etapes"][0]["lat"] == -33.9648
    assert data["etapes"][0]["lon"] == 18.6017


def test_planifier_null_coordinates_when_iata_unknown(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "EUR", "duree_min": 600},
    )
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: None)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["depart"]["lat"] is None and data["depart"]["lon"] is None
    assert data["etapes"][0]["lat"] is None and data["etapes"][0]["lon"] is None


def test_planifier_returns_409_when_infeasible(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "EUR", "duree_min": 600},
    )

    # depart_iata != arrivee_iata : le trajet direct n'est pas gratuit (sinon,
    # depuis le fix Issue 1, une paire de même aéroport coûte 0 et rendrait ce
    # scénario faussement faisable).
    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YYZ",
        "date_debut": "2026-09-01", "date_fin": "2026-09-01", "budget_total": 10,
    })
    assert r.status_code == 409


def test_planifier_converts_prix_devise_to_eur(client, session, monkeypatch):
    """Issue 4 (revue finale) : un prix Duffel renvoyé en devise étrangère (ex.
    USD, comme dans les tests existants) doit être converti en EUR avant
    d'entrer dans cout_transport/cout_total — pas sommé brut."""
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "fetch_offer",
        lambda session, origine, destination, date_ref: {"prix": 500.0, "devise": "USD", "duree_min": 600},
    )
    # Taux fixe déterministe (pas d'appel réseau/yfinance réel) : 1 USD = 0.9 EUR.
    monkeypatch.setattr(voyage_routes.fx, "convert", lambda amount, base, quote, **kw: amount * 0.9)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    # aller + retour à 500 USD chacun -> 450 EUR chacun (taux 0.9) = 900 EUR
    assert data["cout_transport"] == 900.0
    assert data["cout_sejour"] == 160.0  # 2 jours x 80 (EUR, non converti)
    assert data["cout_total"] == 1060.0


def test_planifier_returns_502_when_duffel_unavailable(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(voyage_routes, "fetch_offer", lambda *a, **k: None)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 502


def test_planifier_rejects_visited_lieu(client, session):
    lv = LieuVoyage(nom="Déjà vu", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0, visite=True)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400
    assert "Déjà vu" in r.json()["detail"]


def test_planifier_defaults_depart_et_arrivee_iata_to_yul(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    appels = []

    def fake_fetch_offer(session, origine, destination, date_ref):
        appels.append((origine, destination))
        return {"prix": 500.0, "devise": "EUR", "duree_min": 600}

    monkeypatch.setattr(voyage_routes, "fetch_offer", fake_fetch_offer)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id],
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    origines_destinations = {o for pair in appels for o in pair}
    assert "YUL" in origines_destinations
    assert "CPT" in origines_destinations


def test_planifier_same_iata_pair_does_not_call_duffel(client, session, monkeypatch):
    """Issue 1 (revue finale) : quand depart_iata == arrivee_iata (cas par défaut,
    YUL/YUL), la paire de même aéroport ne doit jamais être envoyée à Duffel — un
    aéroport ne peut pas être pricé contre lui-même. `fetch_offer` ici est un mock
    strict qui échoue (assertion) si jamais appelé avec origine == destination."""
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    def strict_fetch_offer(session, origine, destination, date_ref):
        assert origine != destination, "fetch_offer appelé avec origine == destination"
        return {"prix": 500.0, "devise": "EUR", "duree_min": 600}

    monkeypatch.setattr(voyage_routes, "fetch_offer", strict_fetch_offer)

    # depart_iata/arrivee_iata omis -> défaut YUL/YUL (le cas le plus courant)
    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id],
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200


def test_planifier_arrivee_iata_defaults_to_depart_iata_when_omitted(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    appels = []

    def fake_fetch_offer(session, origine, destination, date_ref):
        appels.append((origine, destination))
        return {"prix": 500.0, "devise": "EUR", "duree_min": 600}

    monkeypatch.setattr(voyage_routes, "fetch_offer", fake_fetch_offer)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YYZ",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    origines_destinations = {o for pair in appels for o in pair}
    assert origines_destinations == {"YYZ", "CPT"}


def test_confirmer_marks_visite(client, session, monkeypatch, tmp_path):
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre"])
    ws.append(["Table Mountain", "Le Cap", "Afrique du Sud", False, None])
    wb.save(p)
    monkeypatch.setattr(voyage_routes, "_voyage_xlsx_path", lambda: p)

    lv = LieuVoyage(nom="Table Mountain", visite=False)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    r = client.post("/voyage/confirmer", json={"lieu_ids": [lv.id]})
    assert r.status_code == 200
    assert session.get(LieuVoyage, lv.id).visite is True
