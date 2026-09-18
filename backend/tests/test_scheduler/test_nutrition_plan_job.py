import datetime as dt
from types import SimpleNamespace

import pandas as pd
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.sante import MesureSante, NutritionGoal, WindowPlan
from app.services.scheduler.jobs import nutrition_plan


def _freeze_today(monkeypatch, d: dt.date):
    """Gèle `nutrition_plan.dt.date.today()` sans toucher au datetime global.

    `timedelta` est exposé tel quel : le job s'en sert le mercredi pour viser
    l'ancre du LENDEMAIN. Un stub qui ne porterait que `date.today` ferait
    planter cette branche-là uniquement — le genre de trou qu'on ne voit qu'un
    mercredi en production.
    """
    monkeypatch.setattr(
        nutrition_plan, "dt",
        SimpleNamespace(date=SimpleNamespace(today=lambda: d), timedelta=dt.timedelta),
    )


def _fake_df():
    # Catalogue factice complet : `calculate_daily_targets` injecte TOUT
    # DAILY_BASE_TARGETS_NUTRIENTS dans les cibles fenêtre, et `optimize_nutrition`
    # construit un array par clé présente -> il faut une colonne par micro.
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres", "Fer",
            "Magnesium", "Omega 3", "VitA", "VitB1", "VitB2", "VitB3", "VitB5", "VitB6",
            "VitB9", "VitB12", "VitD", "VitE", "VitK", "Calcium", "Zinc", "Potassium",
            "Iode", "Selenium", "Phosphore", "Sodium", "Cholesterol", "AG satures", "TotalSugars"]
    data = {
        "Legume": [50, 3, 0.5, 8, 0.4] + [50] * (len(cols) - 5),
        "Riz":    [130, 3, 0.3, 28, 0.2] + [5] * (len(cols) - 5),
        "Poulet": [165, 31, 3.6, 0, 1.2] + [5] * (len(cols) - 5),
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


def test_nutrition_job_generates_when_weight_is_known(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    called = {}

    from app.api.sante import plan as plan_api

    def fake_generate(payload, session):
        called["date"] = payload.date
        return SimpleNamespace(items=[1, 2, 3], intensite="medium")

    monkeypatch.setattr(plan_api, "generate_plan", fake_generate)
    _freeze_today(monkeypatch, dt.date(2026, 7, 21))  # mardi (jour non-ancre) -> plan par jour
    with Session(engine) as session:
        session.add(MesureSante(date=dt.date(2026, 7, 21), poids=70.0))
        session.commit()
        result = nutrition_plan.run(session)

    assert called["date"] == dt.date(2026, 7, 21)
    assert "3 aliments" in result


def test_nutrition_job_skips_cleanly_without_weight(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    _freeze_today(monkeypatch, dt.date(2026, 7, 21))  # mardi (jour non-ancre)
    with Session(engine) as session:
        result = nutrition_plan.run(session)
    assert "aucun poids connu" in result


def test_generates_window_on_monday(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    monkeypatch.setattr(fs, "_verified_catalog", lambda df, day=None: (df, {}, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)
    _freeze_today(monkeypatch, dt.date(2026, 7, 20))  # lundi -> fenêtre 3 jours
    with Session(engine) as session:
        session.add(NutritionGoal(actif=True))
        session.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        session.commit()
        result = nutrition_plan.run(session)
        assert "Fenêtre" in result
        wp = session.exec(
            select(WindowPlan).where(WindowPlan.anchor_date == dt.date(2026, 7, 20))
        ).first()
        assert wp is not None
        assert wp.length == 3


def test_generates_next_window_on_wednesday(monkeypatch):
    """Mercredi = jour de courses de la fenêtre jeu-dim (rabais étudiant lun→mer).
    Le job doit donc générer l'ancre du JEUDI, pas celle du lundi en cours."""
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    monkeypatch.setattr(fs, "_verified_catalog", lambda df, day=None: (df, {}, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)
    _freeze_today(monkeypatch, dt.date(2026, 7, 22))  # mercredi
    with Session(engine) as session:
        session.add(NutritionGoal(actif=True))
        session.add(MesureSante(date=dt.date(2026, 7, 22), poids=51.0))
        session.commit()
        result = nutrition_plan.run(session)
        assert "Fenêtre" in result
        wp = session.exec(
            select(WindowPlan).where(WindowPlan.anchor_date == dt.date(2026, 7, 23))
        ).first()
        assert wp is not None, "la fenêtre du jeudi doit être prête dès le mercredi"
        assert wp.length == 4
        # Et surtout : le mercredi ne doit PAS créer une fenêtre ancrée au lundi.
        assert session.exec(
            select(WindowPlan).where(WindowPlan.anchor_date == dt.date(2026, 7, 20))
        ).first() is None


def test_window_generation_is_idempotent(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    _freeze_today(monkeypatch, dt.date(2026, 7, 20))  # lundi
    with Session(engine) as session:
        # Une fenêtre existe déjà pour l'ancre -> le job ne régénère pas.
        session.add(WindowPlan(anchor_date=dt.date(2026, 7, 20), length=3, food_set={}))
        session.commit()
        result = nutrition_plan.run(session)
    assert "déjà prête" in result
