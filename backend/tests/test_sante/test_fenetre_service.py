import datetime as dt
import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.sante import MesureSante, NutritionGoal, PlanNutrition, WindowPlan


def test_cout_entier_reserve_aux_produits_rapidement_perissables():
    from app.services.sante.fenetre_service import _charge_full_purchase_unit

    assert _charge_full_purchase_unit({
        "href": "/allees/fruits-et-legumes/fruits/bananes/banane/p/1"
    })
    assert _charge_full_purchase_unit({
        "href": "/allees/produits-laitiers-et-oeufs/laits/lait/p/2"
    })
    assert not _charge_full_purchase_unit({
        "href": "/allees/garde-manger/huiles/huile-de-tournesol/p/3"
    })
    assert not _charge_full_purchase_unit({
        "href": "/allees/garde-manger/pates-riz-et-feves/quinoa/p/4"
    })
    assert not _charge_full_purchase_unit({
        "href": "/allees/produits-surgeles/legumes-surgeles/epinards/p/5"
    })


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(NutritionGoal(actif=True))
        s.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        s.commit()
        yield s


def _fake_df():
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


@pytest.fixture(autouse=True)
def _patch_engine_and_prices(monkeypatch, session):
    """Neutralise DB globale, scrape et catalogue réel : df factice + prix identité."""
    import app.core.db as db
    monkeypatch.setattr(db, "engine", session.get_bind())
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)


def test_generate_monday_window_persists_3_days(session):
    from app.services.sante.fenetre_service import generate_window

    wp = generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    assert wp.length == 3
    assert wp.food_set                       # non vide
    days = session.exec(select(PlanNutrition).where(
        PlanNutrition.date >= dt.date(2026, 7, 20))).all()
    assert {d.date for d in days} == {
        dt.date(2026, 7, 20), dt.date(2026, 7, 21), dt.date(2026, 7, 22)}
    # conservation : Σ portions/jour d'un aliment == food_set
    riz = next(iter(wp.food_set))
    total = sum((d.quantites or {}).get(riz, 0.0) for d in days)
    assert total == pytest.approx(wp.food_set[riz], rel=1e-6)


def test_recipe_flours_are_not_optimizer_foods():
    from app.services.sante.fenetre_service import _optimizer_food_allowed

    assert not _optimizer_food_allowed("Farine tout usage")
    assert not _optimizer_food_allowed("Fécule de maïs")
    assert not _optimizer_food_allowed("Masa harina")
    assert _optimizer_food_allowed("Maïs surgelé")
    assert _optimizer_food_allowed("Pain complet")


def test_same_ciqual_profile_keeps_only_cheapest_per_kilo(monkeypatch):
    from app.services.sante import fenetre_service as fs

    df = _fake_df().loc[["Riz", "Poulet"]].copy()
    monkeypatch.setattr(
        "app.services.sante.aliments.load_reservoir_ciqual_refs",
        lambda: {"Riz": "9810", "Poulet": "9810"},
    )
    # Le paquet Poulet coûte davantage, mais son prix vérifié au poids est
    # inférieur : c'est lui qui doit rester parmi deux profils identiques.
    df.loc["Riz", "Prix"] = 0.50
    df.loc["Poulet", "Prix"] = 0.30
    choices = {"Riz": {"price": 2.0}, "Poulet": {"price": 4.0}}
    result, kept_choices = fs._deduplicate_nutrition_twins(df, choices)
    assert list(result.index) == ["Poulet"]
    assert set(kept_choices) == {"Poulet"}


def test_same_superc_upc_is_never_bought_twice(monkeypatch):
    from app.services.sante import fenetre_service as fs

    df = _fake_df().loc[["Riz", "Poulet"]].copy()
    monkeypatch.setattr(
        "app.services.sante.aliments.load_reservoir_ciqual_refs", lambda: {},
    )
    monkeypatch.setattr(
        "app.services.sante.aliments.load_reservoir_product_refs",
        lambda: {"Poulet": "upc-1"},
    )
    # « Riz » représente ici le profil curé; « Poulet », la ligne commerciale
    # du réservoir reliée exactement au même produit Super C.
    choices = {
        "Riz": {"id": "upc-1", "price": 4.0},
        "Poulet": {"id": "upc-1", "price": 4.0},
    }
    result, kept_choices = fs._deduplicate_nutrition_twins(df, choices)

    assert list(result.index) == ["Riz"]
    assert set(kept_choices) == {"Riz"}


def test_liste_du_haut_garde_le_cout_consomme_et_non_le_prix_du_paquet():
    from app.services.sante.fenetre_service import _attach_cart_prices

    shopping = [{
        "aliment": "Huile", "quantite_g": 3.0, "prix": 0.02,
        "promo": False,
    }]
    cart = [{
        "aliment": "Huile", "product_id": "oil-1",
        "product_name": "Selection Huile", "href": "/p/oil-1",
        "format": "946 mL", "qty": 1, "prix_estime": 7.19,
        "a_verifier": False, "promo": False,
    }]

    result = _attach_cart_prices(shopping, cart)

    assert result[0]["prix"] == pytest.approx(0.02)
    assert result[0]["prix_unitaire"] == pytest.approx(7.19)
    assert result[0]["prix_verifie"] is True


def test_liste_de_courses_finale_est_triee_par_cout_consomme_decroissant(
    session, monkeypatch,
):
    from app.services.sante import fenetre_service as fs

    wp = fs.generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    prices = [item["prix"] for item in wp.shopping_list if item.get("prix") is not None]
    assert prices == sorted(prices, reverse=True)


def test_only_one_juice_or_nectar_variant_is_kept(monkeypatch):
    from app.services.sante import fenetre_service as fs

    df = _fake_df().copy()
    df.index = ["Oasis Jus de mangue", "Smoothie super vert", "Epinards"]
    monkeypatch.setattr(
        "app.services.sante.aliments.load_reservoir_ciqual_refs", lambda: {},
    )
    choices = {
        "Oasis Jus de mangue": {"price": 1.1},
        "Smoothie super vert": {"price": 4.49},
        "Epinards": {"price": 3.0},
    }
    df.loc["Oasis Jus de mangue", "Prix"] = 0.10
    df.loc["Smoothie super vert", "Prix"] = 0.25
    result, _ = fs._deduplicate_nutrition_twins(df, choices)
    assert "Oasis Jus de mangue" in result.index
    assert "Smoothie super vert" not in result.index
    assert "Epinards" in result.index


def test_pate_de_tomate_est_plafonnee_comme_concentre():
    from app.services.sante.fenetre_service import _apply_practical_quantity_caps

    df = _fake_df().loc[["Riz"]].copy()
    df.index = ["Pate de tomate"]
    df.loc["Pate de tomate", "MaxQty"] = 300.0
    result = _apply_practical_quantity_caps(df)
    assert result.loc["Pate de tomate", "MaxQty"] == pytest.approx(60.0)


def test_caps_pratiques_reconnaissent_aussi_les_noms_commerciaux():
    from app.services.sante.fenetre_service import _apply_practical_quantity_caps

    df = pd.concat([_fake_df().loc[["Riz"]]] * 3)
    df.index = [
        "Pastene Tomates séchées au soleil",
        "Irrésistible Sirop d'érable ambré",
        "Ox Head Riz blanc parfumé",
    ]
    df["MaxQty"] = 300.0
    result = _apply_practical_quantity_caps(df)
    assert result.loc["Pastene Tomates séchées au soleil", "MaxQty"] == 30.0
    assert result.loc["Irrésistible Sirop d'érable ambré", "MaxQty"] == 25.0
    assert result.loc["Ox Head Riz blanc parfumé", "MaxQty"] == 250.0


def test_debt_from_previous_window_consumption(session):
    """Une fenêtre précédente sous-consommée en VitD escalade sa priorité."""
    from app.services.sante.fenetre_service import generate_window
    # fenêtre précédente (jeu 2026-07-16 → 4 jours) avec conso VitD faible
    for d in [dt.date(2026, 7, 16), dt.date(2026, 7, 17),
              dt.date(2026, 7, 18), dt.date(2026, 7, 19)]:
        session.add(PlanNutrition(
            date=d, targets={"VitD": 15.0}, consumed={"VitD": 1.0}))
    session.add(WindowPlan(anchor_date=dt.date(2026, 7, 16), length=4,
                           food_set={}, debt_series={"VitD": 1}))
    session.commit()
    wp = generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    assert wp.debt_series.get("VitD", 0) >= 2   # série incrémentée


def test_pantry_deducts_from_shopping_and_cout_a_payer(session, monkeypatch):
    """Garde-manger : le stock est déduit de la liste + du coût à payer, mais le
    coût catalogue (cout_total, qui pilote le ratio) reste ≥ le coût à payer."""
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "_load_pantry_items", lambda: [
        {"ingredient": "Legume", "quantite": 100, "unite": "kg"}])  # stock massif
    wp = fs.generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    legume_food = wp.food_set.get("Legume", 0.0)
    legume_ship = next((it for it in wp.shopping_list if it["aliment"] == "Legume"), None)
    if legume_food > 0:
        # massivement en stock -> retiré de la liste, ou reste à acheter < besoin
        assert legume_ship is None or legume_ship["a_acheter_g"] < legume_food
    assert wp.score["cout_a_payer"] <= wp.score["cout_total"] + 1e-6
