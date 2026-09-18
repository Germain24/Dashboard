import datetime as dt
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.main import app
from app.core.db import get_session
from app.models.sante import MesureSante, NutritionGoal
from app.models.agenda import Evenement


def _fake_df():
    # NOTE : le brief ne demandait d'ajouter que Sodium/Cholesterol/AG
    # satures/TotalSugars, mais `calculate_daily_targets` fusionne TOUT
    # `DAILY_BASE_TARGETS_NUTRIENTS` (25+ clés micro) dans les cibles fenêtre,
    # et `optimize_nutrition` construit `nutrient_arrays` pour CHAQUE clé
    # présente dans les targets -> KeyError sur le premier micro manquant
    # (constaté : 'Magnesium', avant même 'Sodium'). Colonnes alignées sur le
    # fixture déjà prouvé de `test_fenetre_service.py` (Task 8), qui traverse
    # exactement le même chemin `generate_window` -> `optimize_ratio` ->
    # `optimize_nutrition`.
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


@pytest.fixture
def client(monkeypatch):
    # poolclass=StaticPool : FastAPI exécute les endpoints sync via un worker
    # thread (anyio.to_thread.run_sync), différent du thread pytest qui crée
    # les tables ci-dessous. Sans StaticPool, SingletonThreadPool (défaut
    # sqlite:// en mémoire) donnerait à ce worker thread une connexion —
    # donc une base :memory: — neuve et vide -> "no such table". Cf. doc
    # FastAPI officielle sur les tests avec SQLite en mémoire.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(NutritionGoal(actif=True))
        s.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        s.commit()
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)
    monkeypatch.setattr(fs, "refresh_prices_best_effort", lambda: False)
    # Le routeur reconstruit les items/jour depuis son propre chargeur → le
    # patcher aussi pour que la réponse reflète le df factice.
    import app.api.sante.fenetre as fenetre_api
    monkeypatch.setattr(fenetre_api, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fenetre_api, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    app.dependency_overrides[get_session] = lambda: Session(engine)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_generate_then_get_current(client):
    r = client.post("/sante/fenetre/generate", json={"date": "2026-07-20", "poids": 51.0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["length"] == 3
    assert len(body["jours"]) == 3
    assert any(j["items"] for j in body["jours"])   # portions/jour reconstruites
    assert body["shopping_list"]
    assert "ratio" in body["score"]
    assert body["score"]["equilibre_macros"] > 0
    assert body["score"]["equilibre_moyen"] > 0

    r2 = client.get("/sante/fenetre/current", params={"date": "2026-07-21"})
    assert r2.status_code == 200
    assert r2.json()["anchor_date"] == "2026-07-20"


def test_work_coupon_is_included_in_window_plan(client):
    session = app.dependency_overrides[get_session]()
    session.add(Evenement(
        titre="Shift", debut=dt.datetime(2026, 7, 20, 11),
        fin=dt.datetime(2026, 7, 20, 16), categorie="travail",
    ))
    session.commit()
    session.close()

    response = client.post("/sante/fenetre/generate", json={"date": "2026-07-20", "poids": 51.0})
    assert response.status_code == 200, response.text
    day = response.json()["jours"][0]
    assert len(day["repas_travail"]) == 1
    assert day["repas_travail"][0]["credit_couvert"] <= 30
    assert day["repas_travail"][0]["reste_a_payer"] == max(
        0, round(day["repas_travail"][0]["price"] - 30, 2))
    assert day["repas_travail"][0]["macros_estimees"] is True
    # Les totaux quotidiens incluent bien le plat au restaurant.
    assert day["totals"]["Calories"] >= day["repas_travail"][0]["calories"]


def test_opening_sante_can_trigger_non_blocking_store_refresh(client, monkeypatch):
    from app.services.sante import fenetre_service as fs

    calls = []
    monkeypatch.setattr(fs, "refresh_prices_best_effort", lambda: calls.append(True) or True)
    response = client.post("/sante/store-pricing/refresh-if-stale")

    assert response.status_code == 202
    assert response.json() == {"started": True}
    assert calls == [True]
