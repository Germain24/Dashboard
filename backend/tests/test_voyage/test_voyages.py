"""Voyage confirmé : checklist par voyage + budget par étape (§5.4).

Le service travaille sur l'entité `Voyage` créée par POST /voyage/confirmer ;
l'agrégation budgétaire est pure (aucune session).
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.models.voyage import LieuVoyage, VoyageEtape
from app.services.voyage.voyages import (
    CHECKLIST_DEFAUT,
    add_checklist_item,
    aggregate_budget,
    budget_etape,
    create_voyage,
    delete_checklist_item,
    delete_voyage,
    get_voyage,
    list_voyages,
    set_cout_reel,
    update_checklist_item,
    voyage_checklist,
    voyage_etapes,
)


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


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


def _etape(lieu_id: int, jours: int = 3) -> dict:
    return {
        "lieu_id": lieu_id, "jours": jours,
        "date_arrivee": dt.date(2026, 8, 1), "date_depart": dt.date(2026, 8, 1 + jours),
    }


# ── budget_etape : s'appuie sur costs.cost_breakdown ──────────────────────────

def test_budget_etape_reprend_la_ventilation_de_costs(lieu):
    # 3 jours * (60 + 40) + activité 50 + transport local 30
    assert budget_etape(lieu, 3) == 380.0


def test_budget_etape_zero_jour(lieu):
    """Un lieu sans nuitée garde ses coûts fixes (activité + transport local)."""
    assert budget_etape(lieu, 0) == 80.0


# ── aggregate_budget : pur ────────────────────────────────────────────────────

def test_aggregate_budget_sans_cout_reel():
    etapes = [
        VoyageEtape(voyage_id=1, nom="A", cout_estime=380.0),
        VoyageEtape(voyage_id=1, nom="B", cout_estime=120.0),
    ]
    agg = aggregate_budget(etapes)
    assert agg["cout_estime_total"] == 500.0
    assert agg["cout_reel_total"] == 0.0
    assert agg["cout_projete_total"] == 500.0
    assert agg["ecart"] == 0.0
    assert agg["etapes_avec_cout_reel"] == 0


def test_aggregate_budget_melange_reel_et_estime():
    """Le projeté remplace l'estimé étape par étape dès qu'un réel est saisi."""
    etapes = [
        VoyageEtape(voyage_id=1, nom="A", cout_estime=380.0, cout_reel=420.0),
        VoyageEtape(voyage_id=1, nom="B", cout_estime=120.0),
    ]
    agg = aggregate_budget(etapes)
    assert agg["cout_estime_total"] == 500.0
    assert agg["cout_reel_total"] == 420.0
    assert agg["cout_projete_total"] == 540.0
    assert agg["ecart"] == 40.0
    assert agg["etapes_avec_cout_reel"] == 1


def test_aggregate_budget_vide():
    agg = aggregate_budget([])
    assert agg == {
        "cout_estime_total": 0.0, "cout_reel_total": 0.0,
        "cout_projete_total": 0.0, "ecart": 0.0, "etapes_avec_cout_reel": 0,
    }


# ── création du voyage ────────────────────────────────────────────────────────

def test_create_voyage_calcule_le_cout_estime_de_chaque_etape(session, lieu):
    v = create_voyage(
        session, titre="Afrique du Sud",
        date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 15),
        etapes=[_etape(lieu.id, 3)],
    )
    etapes = voyage_etapes(session, v.id)
    assert len(etapes) == 1
    assert etapes[0].cout_estime == 380.0
    assert etapes[0].cout_reel is None
    assert etapes[0].ordre == 0


def test_create_voyage_denormalise_le_lieu(session, lieu):
    """`lieu_voyage` est réécrit à chaque sync Excel (ids non stables) : le nom
    doit survivre à une resynchro, donc être copié sur l'étape."""
    v = create_voyage(
        session, titre="Afrique du Sud",
        date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 15),
        etapes=[_etape(lieu.id, 3)],
    )
    for old in session.exec(select(LieuVoyage)).all():
        session.delete(old)
    session.commit()

    etapes = voyage_etapes(session, v.id)
    assert etapes[0].nom == "Table Mountain"
    assert etapes[0].pays == "Afrique du Sud"


def test_create_voyage_seed_la_checklist_par_defaut(session, lieu):
    v = create_voyage(
        session, titre="Afrique du Sud",
        date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 15),
        etapes=[_etape(lieu.id)],
    )
    items = voyage_checklist(session, v.id)
    assert [i.label for i in items] == list(CHECKLIST_DEFAUT)
    assert all(i.fait is False for i in items)
    assert [i.ordre for i in items] == list(range(len(CHECKLIST_DEFAUT)))


def test_create_voyage_sans_checklist_par_defaut(session, lieu):
    v = create_voyage(
        session, titre="Sec", date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 5),
        etapes=[_etape(lieu.id)], checklist_defaut=False,
    )
    assert voyage_checklist(session, v.id) == []


def test_create_voyage_etape_lieu_inconnu(session):
    with pytest.raises(ValueError, match="introuvable"):
        create_voyage(
            session, titre="X", date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 5),
            etapes=[_etape(999)],
        )


# ── CRUD voyage ───────────────────────────────────────────────────────────────

def test_list_get_delete_voyage(session, lieu):
    v = create_voyage(
        session, titre="Afrique du Sud",
        date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 15),
        etapes=[_etape(lieu.id)],
    )
    assert [x.id for x in list_voyages(session)] == [v.id]
    assert get_voyage(session, v.id).titre == "Afrique du Sud"
    assert delete_voyage(session, v.id) is True
    assert list_voyages(session) == []
    # Les enfants partent avec le voyage (pas d'orphelins).
    assert voyage_etapes(session, v.id) == []
    assert voyage_checklist(session, v.id) == []
    assert delete_voyage(session, v.id) is False


# ── checklist CRUD scoped voyage ──────────────────────────────────────────────

def test_checklist_crud(session, lieu):
    v = create_voyage(
        session, titre="X", date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 5),
        etapes=[_etape(lieu.id)], checklist_defaut=False,
    )
    a = add_checklist_item(session, v.id, "Passeport")
    b = add_checklist_item(session, v.id, "Vaccins")
    assert [i.ordre for i in voyage_checklist(session, v.id)] == [0, 1]

    updated = update_checklist_item(session, v.id, a.id, fait=True)
    assert updated.fait is True
    assert update_checklist_item(session, v.id, b.id, label="Vaccins à jour").label == "Vaccins à jour"

    assert delete_checklist_item(session, v.id, a.id) is True
    assert [i.label for i in voyage_checklist(session, v.id)] == ["Vaccins à jour"]
    assert delete_checklist_item(session, v.id, a.id) is False


def test_checklist_item_isole_par_voyage(session, lieu):
    """Un item ne doit pas être modifiable via l'id d'un autre voyage."""
    v1 = create_voyage(session, titre="V1", date_debut=dt.date(2026, 8, 1),
                       date_fin=dt.date(2026, 8, 5), etapes=[_etape(lieu.id)],
                       checklist_defaut=False)
    v2 = create_voyage(session, titre="V2", date_debut=dt.date(2026, 9, 1),
                       date_fin=dt.date(2026, 9, 5), etapes=[_etape(lieu.id)],
                       checklist_defaut=False)
    item = add_checklist_item(session, v1.id, "Passeport")
    assert update_checklist_item(session, v2.id, item.id, fait=True) is None
    assert delete_checklist_item(session, v2.id, item.id) is False


# ── budget par étape ──────────────────────────────────────────────────────────

def test_set_cout_reel(session, lieu):
    v = create_voyage(
        session, titre="X", date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 5),
        etapes=[_etape(lieu.id, 3)], checklist_defaut=False,
    )
    etape = voyage_etapes(session, v.id)[0]
    assert set_cout_reel(session, v.id, etape.id, 420.0).cout_reel == 420.0
    assert aggregate_budget(voyage_etapes(session, v.id))["ecart"] == 40.0
    # None efface la saisie et fait retomber le projeté sur l'estimé.
    assert set_cout_reel(session, v.id, etape.id, None).cout_reel is None
    assert aggregate_budget(voyage_etapes(session, v.id))["ecart"] == 0.0


def test_set_cout_reel_etape_inconnue(session, lieu):
    v = create_voyage(
        session, titre="X", date_debut=dt.date(2026, 8, 1), date_fin=dt.date(2026, 8, 5),
        etapes=[_etape(lieu.id)], checklist_defaut=False,
    )
    assert set_cout_reel(session, v.id, 9999, 10.0) is None
