import datetime as dt
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.skincare import SkincareProduct
from app.services.skincare import products as svc


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_and_list(session):
    svc.create_product(session, {"nom": "Nettoyant", "type": "nettoyant", "moment": "AM", "ordre": 0})
    svc.create_product(session, {"nom": "Hydratant", "type": "hydratant", "moment": "AM", "ordre": 1})
    items = svc.list_products(session)
    assert [p.nom for p in items] == ["Nettoyant", "Hydratant"]  # triés par moment puis ordre


def test_routine_for_moment_is_ordered(session):
    svc.create_product(session, {"nom": "B", "moment": "PM", "ordre": 2})
    svc.create_product(session, {"nom": "A", "moment": "PM", "ordre": 1})
    routine = svc.routine_for(session, "PM")
    assert [p.nom for p in routine] == ["A", "B"]


def test_due_today_excludes_inactive_and_wrong_weekday(session):
    # 2026-06-02 = mardi (weekday 1)
    svc.create_product(session, {"nom": "Quotidien", "moment": "AM", "frequence_type": "quotidien"})
    svc.create_product(session, {"nom": "Lundi seulement", "moment": "AM",
                                 "frequence_type": "hebdo_jours", "frequence_jours": "0"})
    due = svc.due_on(session, dt.date(2026, 6, 2))
    noms = {p.nom for p in due}
    assert "Quotidien" in noms
    assert "Lundi seulement" not in noms


def test_products_to_repurchase_flags_low_stock_and_expired(session):
    svc.create_product(session, {"nom": "Presque vide", "stock_qte": 0.0})
    svc.create_product(session, {"nom": "Périmé", "stock_qte": 5.0,
                                 "date_peremption": dt.date(2020, 1, 1)})
    svc.create_product(session, {"nom": "OK", "stock_qte": 5.0})
    noms = {p.nom for p in svc.to_repurchase(session, today=dt.date(2026, 6, 2))}
    assert noms == {"Presque vide", "Périmé"}
