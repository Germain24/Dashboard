import datetime as dt
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine

from app.models.sante import MesureSante
from app.services.scheduler.jobs import nutrition_plan


def test_nutrition_job_generates_when_weight_is_known(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    called = {}

    from app.api.sante import plan as plan_api

    def fake_generate(payload, session):
        called["date"] = payload.date
        called["session"] = session
        return SimpleNamespace(items=[1, 2, 3], intensite="medium")

    monkeypatch.setattr(plan_api, "generate_plan", fake_generate)
    with Session(engine) as session:
        session.add(MesureSante(date=dt.date.today(), poids=70.0))
        session.commit()
        result = nutrition_plan.run(session)

    assert called["date"] == dt.date.today()
    assert "3 aliments" in result


def test_nutrition_job_skips_cleanly_without_weight():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        result = nutrition_plan.run(session)
    assert "aucun poids connu" in result
