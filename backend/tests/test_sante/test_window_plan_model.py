import datetime as dt
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401  (enregistre les tables)
from app.models.sante import WindowPlan


def test_window_plan_roundtrip():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(WindowPlan(
            anchor_date=dt.date(2026, 7, 20), length=3, poids_used=51.0,
            food_set={"Riz": 900.0}, shopping_list=[{"aliment": "Riz", "quantite_g": 900.0}],
            score={"ratio": 0.02}, debt_series={"VitD": 1},
        ))
        s.commit()
        row = s.exec(select(WindowPlan).where(WindowPlan.anchor_date == dt.date(2026, 7, 20))).one()
        assert row.length == 3
        assert row.food_set["Riz"] == 900.0
        assert row.debt_series["VitD"] == 1
