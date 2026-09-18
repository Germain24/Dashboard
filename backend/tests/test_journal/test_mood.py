import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.journal import mood as svc


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_upsert_creates_then_updates_same_day(session):
    d = dt.date(2026, 6, 1)
    e1 = svc.upsert_entry(session, d, humeur=3, energie=4, tags=["calme"], note="ok")
    assert e1.id is not None and e1.humeur == 3
    e2 = svc.upsert_entry(session, d, humeur=5, energie=2, tags=["motivé"], note="mieux")
    assert e2.id == e1.id          # même jour -> update, pas de doublon
    assert e2.humeur == 5 and e2.tags == ["motivé"]
    assert len(svc.list_entries(session, d, d)) == 1


def test_upsert_rejects_out_of_range(session):
    with pytest.raises(ValueError):
        svc.upsert_entry(session, dt.date(2026, 6, 1), humeur=6, energie=3, tags=[], note="")


from app.services.journal.mood import mood_trends


def test_mood_trends_aggregates():
    entries = [
        {"date": "2026-06-01", "humeur": 2, "energie": 3, "tags": ["calme"]},
        {"date": "2026-06-02", "humeur": 4, "energie": 5, "tags": ["calme", "motivé"]},
    ]
    t = mood_trends(entries)
    assert t["n"] == 2
    assert t["moyenne_humeur"] == 3.0
    assert t["distribution_humeur"]["2"] == 1 and t["distribution_humeur"]["4"] == 1
    assert t["tags_freq"][0] == {"tag": "calme", "count": 2}


def test_mood_trends_empty():
    t = mood_trends([])
    assert t["n"] == 0 and t["tags_freq"] == []
