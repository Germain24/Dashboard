"""API Voyage : sync, lieux, planifier, confirmer."""
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


def test_get_suggestions_sorts_by_distance(client, session, monkeypatch):
    """L'endpoint /suggerer doit renvoyer les lieux non visités par distance
    croissante depuis depart_iata, sans exiger de sélection manuelle."""
    proche = LieuVoyage(nom="Bogota", aeroport_iata="BOG", jours_min=2, jours_max=4, cout_jour_estime=40.0)
    loin = LieuVoyage(nom="Tokyo", aeroport_iata="HND", jours_min=2, jours_max=4, cout_jour_estime=100.0)
    visite = LieuVoyage(nom="Deja vu", aeroport_iata="LIM", jours_min=2, jours_max=4,
                         cout_jour_estime=50.0, visite=True)
    incomplet = LieuVoyage(nom="Incomplet")
    session.add_all([proche, loin, visite, incomplet])
    session.commit()

    coords = {
        "YUL": (45.4706, -73.7408), "BOG": (4.7016, -74.1469),
        "HND": (35.5494, 139.7798), "LIM": (-12.0219, -77.1143),
    }
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: coords.get(iata))

    r = client.get("/voyage/suggerer", params={"depart_iata": "YUL"})
    assert r.status_code == 200
    data = r.json()
    noms = [d["nom"] for d in data]
    assert noms == ["Bogota", "Tokyo"]   # visité + incomplet exclus, trié par distance
    assert data[0]["distance_km"] < data[1]["distance_km"]


def test_get_suggestions_respects_limit(client, session, monkeypatch):
    coords = {"YUL": (45.4706, -73.7408)}
    for i in range(5):
        lv = LieuVoyage(nom=f"L{i}", aeroport_iata=f"A{i}", jours_min=1, jours_max=1, cout_jour_estime=10.0)
        session.add(lv)
        coords[f"A{i}"] = (float(i), float(i))
    session.commit()
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: coords.get(iata))

    r = client.get("/voyage/suggerer", params={"depart_iata": "YUL", "limit": 2})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_suggestions_unknown_depart_iata(client, monkeypatch):
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: None)
    r = client.get("/voyage/suggerer", params={"depart_iata": "ZZZ"})
    assert r.status_code == 404


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
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 500.0, "duree_min": 600},
    )

    r = client.post("/voyage/planifier", json={
        # date_fin pile 4 jours après date_debut (2 jours de trajet + 2 de
        # séjour min) -- aucune marge de jours, donc le remplissage des jours
        # restants (cf. solver._remplir_jours_restants) ne s'applique pas ici,
        # ce test vérifie juste l'agrégation transport/séjour de base.
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-05", "budget_total": 10000,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["etapes"]) == 1
    assert data["etapes"][0]["lieu_id"] == lv.id
    assert data["etapes"][0]["jours"] == 2
    # aller + retour à 500 chacun (1000) + subsistance en transit (YUL a un
    # coût/jour de 0, seul CPT compte : 2 legs x 0.5x80x1.2 = 96) = 1096.
    assert data["cout_transport"] == 1096.0
    assert data["cout_sejour"] == 160.0  # 2 jours x 80
    assert data["cout_hebergement"] == 104.0
    assert data["cout_nourriture"] == 56.0
    assert data["cout_activites"] == 28.8
    assert data["cout_transport_local"] == 28.8
    assert data["cout_total"] == 1313.6


def test_planifier_includes_coordinates(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 500.0, "duree_min": 600},
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
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 500.0, "duree_min": 600},
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
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 500.0, "duree_min": 600},
    )

    # depart_iata != arrivee_iata : le trajet direct n'est pas gratuit (sinon,
    # depuis le fix Issue 1, une paire de même aéroport coûte 0 et rendrait ce
    # scénario faussement faisable).
    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YYZ",
        "date_debut": "2026-09-01", "date_fin": "2026-09-01", "budget_total": 10,
    })
    assert r.status_code == 409


def test_planifier_returns_400_when_airport_unknown(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    monkeypatch.setattr(voyage_routes, "estimate_trajet", lambda *a, **k: None)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YUL", "arrivee_iata": "YUL",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 400


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

    def fake_estimate_trajet(origine, destination):
        appels.append((origine, destination))
        return {"prix": 500.0, "duree_min": 600}

    monkeypatch.setattr(voyage_routes, "estimate_trajet", fake_estimate_trajet)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id],
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    origines_destinations = {o for pair in appels for o in pair}
    assert "YUL" in origines_destinations
    assert "CPT" in origines_destinations


def test_planifier_same_iata_pair_does_not_call_estimate_trajet(client, session, monkeypatch):
    """Issue 1 (revue finale) : quand depart_iata == arrivee_iata (cas par défaut,
    YUL/YUL), la paire de même aéroport ne doit jamais être estimée — un aéroport
    ne peut pas être pricé contre lui-même. `estimate_trajet` ici est un mock
    strict qui échoue (assertion) si jamais appelé avec origine == destination."""
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2,
                     cout_jour_estime=80.0)
    session.add(lv)
    session.commit()
    session.refresh(lv)

    def strict_estimate_trajet(origine, destination):
        assert origine != destination, "estimate_trajet appelé avec origine == destination"
        return {"prix": 500.0, "duree_min": 600}

    monkeypatch.setattr(voyage_routes, "estimate_trajet", strict_estimate_trajet)

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

    def fake_estimate_trajet(origine, destination):
        appels.append((origine, destination))
        return {"prix": 500.0, "duree_min": 600}

    monkeypatch.setattr(voyage_routes, "estimate_trajet", fake_estimate_trajet)

    r = client.post("/voyage/planifier", json={
        "candidats": [lv.id], "depart_iata": "YYZ",
        "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 200
    origines_destinations = {o for pair in appels for o in pair}
    assert origines_destinations == {"YYZ", "CPT"}


def test_planifier_auto_selects_candidates_and_returns_multiple_itineraries(client, session, monkeypatch):
    """Bout-en-bout de /planifier-auto : aucun `candidats` fourni -- l'utilisateur
    donne juste départ/dates/budget, et reçoit plusieurs itinéraires distincts."""
    proche = LieuVoyage(nom="Bogota", aeroport_iata="BOG", jours_min=2, jours_max=2, cout_jour_estime=40.0)
    loin = LieuVoyage(nom="Lima", aeroport_iata="LIM", jours_min=2, jours_max=2, cout_jour_estime=40.0)
    session.add_all([proche, loin])
    session.commit()

    coords = {"YUL": (45.4706, -73.7408), "BOG": (4.7016, -74.1469), "LIM": (-12.0219, -77.1143)}
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: coords.get(iata))
    monkeypatch.setattr(
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 300.0, "duree_min": 300},
    )

    r = client.post("/voyage/planifier-auto", json={
        "depart_iata": "YUL", "date_debut": "2026-09-01", "date_fin": "2026-09-10",
        "budget_total": 10000, "k": 5,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["itineraires"]) >= 1
    # Budget/temps larges -> les deux lieux tiennent ensemble : le meilleur
    # itinéraire doit les inclure tous les deux.
    assert len(data["itineraires"][0]["etapes"]) == 2


def test_planifier_auto_unknown_depart_iata(client, monkeypatch):
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: None)
    r = client.post("/voyage/planifier-auto", json={
        "depart_iata": "ZZZ", "date_debut": "2026-09-01", "date_fin": "2026-09-10", "budget_total": 10000,
    })
    assert r.status_code == 404


def test_planifier_auto_returns_409_when_infeasible(client, session, monkeypatch):
    lv = LieuVoyage(nom="Table Mountain", aeroport_iata="CPT", jours_min=2, jours_max=2, cout_jour_estime=80.0)
    session.add(lv)
    session.commit()

    coords = {"YUL": (45.4706, -73.7408), "CPT": (-33.9648, 18.6017)}
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: coords.get(iata))
    monkeypatch.setattr(
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 500.0, "duree_min": 600},
    )
    r = client.post("/voyage/planifier-auto", json={
        "depart_iata": "YUL", "date_debut": "2026-09-01", "date_fin": "2026-09-01", "budget_total": 10,
    })
    assert r.status_code == 409


def test_planifier_auto_respects_open_jaw_geographic_corridor(client, session, monkeypatch):
    iceland = LieuVoyage(
        nom="Reykjavik", ville="Reykjavik", pays="Islande", aeroport_iata="KEF",
        jours_min=2, jours_max=3, cout_jour_estime=100.0,
    )
    australia = LieuVoyage(
        nom="Sydney", ville="Sydney", pays="Australie", aeroport_iata="SYD",
        jours_min=2, jours_max=3, cout_jour_estime=100.0,
    )
    session.add_all([iceland, australia])
    session.commit()
    coords = {
        "YUL": (45.4706, -73.7408), "CDG": (49.0097, 2.5479),
        "KEF": (63.985, -22.6056), "SYD": (-33.9399, 151.1753),
    }
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: coords.get(iata))
    monkeypatch.setattr(
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 300.0, "duree_min": 300},
    )

    response = client.post("/voyage/planifier-auto", json={
        "depart_iata": "YUL", "arrivee_iata": "CDG",
        "date_debut": "2026-09-01", "date_fin": "2026-09-15",
        "budget_total": 15000, "k": 2, "prix_live": False,
    })
    assert response.status_code == 200
    names = {
        step["nom"]
        for itinerary in response.json()["itineraires"]
        for step in itinerary["etapes"]
    }
    assert "Reykjavik" in names
    assert "Sydney" not in names


def test_planifier_auto_excludes_impossible_activities(client, session, monkeypatch):
    allowed = LieuVoyage(
        nom="Bogota", pays="Colombie", aeroport_iata="BOG",
        jours_min=2, jours_max=3, cout_jour_estime=70,
    )
    forbidden = LieuVoyage(
        nom="Pyongyang", pays="Corée du Nord", aeroport_iata="FNJ",
        jours_min=2, jours_max=3, cout_jour_estime=70,
        statut="impossible", raison_indisponible="Évitez tout voyage",
    )
    session.add_all([allowed, forbidden])
    session.commit()
    coords = {
        "YUL": (45.4706, -73.7408), "BOG": (4.7016, -74.1469),
        "FNJ": (39.224, 125.67),
    }
    monkeypatch.setattr(voyage_routes, "lookup_coords", lambda iata, **kwargs: coords.get(iata))
    monkeypatch.setattr(
        voyage_routes, "estimate_trajet",
        lambda origine, destination: {"prix": 300.0, "duree_min": 300},
    )

    response = client.post("/voyage/planifier-auto", json={
        "depart_iata": "YUL", "date_debut": "2026-09-01", "date_fin": "2026-09-10",
        "budget_total": 3000, "k": 1, "prix_live": False,
    })
    assert response.status_code == 200
    names = {step["nom"] for step in response.json()["itineraires"][0]["etapes"]}
    assert names == {"Bogota"}


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
