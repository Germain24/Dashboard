from app.services.sante.common_foods import (
    COMMON_FOOD_CODES,
    SUPER_C_EXPANSION_CODES,
    load_common_foods,
)
from app.services.sante.fenetre_service import OPTIMIZER_PRIORITY_FOODS
from app.services.sante.superc_catalog_rebuild import CATALOG_MAP


def test_common_foods_have_ciqual_profiles_without_invented_prices():
    foods = load_common_foods()

    assert set(foods) == set(COMMON_FOOD_CODES)
    assert foods["Pomme de terre"]["Energie"] > 0
    assert foods["Chou kale"]["VitK"] > 0
    assert foods["Sel iode"]["Iode"] > 0
    assert all(profile["Prix"] == 0 for profile in foods.values())


def test_superc_expansion_adds_exactly_thirty_ciqual_foods():
    foods = load_common_foods()
    assert len(SUPER_C_EXPANSION_CODES) == 30
    assert set(SUPER_C_EXPANSION_CODES) <= set(foods)
    assert foods["Palourdes en conserve"]["Iode"] > 0
    assert foods["Huile de tournesol"]["VitE"] > 0
    assert foods["Pate de tomate"]["Potassium"] > 0
    assert foods["Thon jaune en conserve"]["VitB3"] > 0


def test_noyau_sportif_est_structurellement_disponible_au_solveur():
    """Chaque aliment demandé a un profil, une recherche Super C et une place
    protégée dans la shortlist. Le prix live reste naturellement requis."""
    from app.services.cuisine.store_categories import search_keywords
    from app.services.sante.aliments import load_aliments_dataframe

    df = load_aliments_dataframe(include_reservoir=True)
    assert OPTIMIZER_PRIORITY_FOODS <= set(df.index)
    assert OPTIMIZER_PRIORITY_FOODS <= set(CATALOG_MAP)
    assert all(search_keywords(name) for name in OPTIMIZER_PRIORITY_FOODS)


def test_yogourt_grec_2_pourcent_est_derive_du_profil_nature_cure():
    from app.services.sante.aliments import load_aliments_dataframe

    df = load_aliments_dataframe()
    base = df.loc["Yogourt grec nature 0%"]
    greek_2 = df.loc["Yogourt grec nature 2%"]
    assert greek_2["Proteines"] == base["Proteines"]
    assert greek_2["Lipides"] == 2.0
    assert greek_2["Energie"] == base["Energie"] + 18.0
    assert greek_2["MaxQty"] == 400.0


def test_epices_concentrees_ont_des_plafonds_realistes():
    foods = load_common_foods()
    assert foods["Cannelle moulue"]["MaxQty"] == 5.0
    assert foods["Cacao non sucre en poudre"]["MaxQty"] == 30.0
