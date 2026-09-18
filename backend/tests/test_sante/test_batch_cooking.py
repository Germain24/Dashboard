"""Optimisation conjointe 2 tacos + 1 pot CREAMi + complément frais.

Les tests portent sur un mini-catalogue construit ici : le vrai catalogue rend
chaque optimisation trop lente pour une suite de tests (~3 min), et surtout les
propriétés vérifiées (pas de surplus, structure imposée, séparation des blocs)
ne dépendent pas de sa richesse.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.sante import batch_cooking as bc

# Colonnes minimales attendues par l'optimiseur.
_COLS = [
    "Prix", "Energie", "Proteines", "Lipides", "Glucides", "Fibres",
    "Calcium", "Fer", "VitC", "VitD", "Potassium", "Magnesium", "Sodium",
    "Zinc", "VitB12", "VitB9", "VitA", "VitE", "Iode", "Selenium",
    "MinQty", "MaxQty", "Congelable", "CreamiOk",
]


def _aliment(prix, kcal, prot, *, congelable=1, creami=0, minq=10, **micros):
    ligne = {c: 0.0 for c in _COLS}
    ligne.update({"Prix": prix, "Energie": kcal, "Proteines": prot,
                  "MinQty": minq, "MaxQty": 0,
                  "Congelable": congelable, "CreamiOk": creami})
    ligne.update(micros)
    return ligne


@pytest.fixture
def catalogue() -> pd.DataFrame:
    """Mini-catalogue couvrant chaque famille de la base imposée."""
    data = {
        "Tortilla de mais": _aliment(0.30, 218, 5.7, minq=30, Calcium=81),
        "Maquereau": _aliment(0.80, 205, 19.0, VitD=8.0, Selenium=44),
        "Epinards": _aliment(0.50, 23, 2.9, VitC=28, Fer=2.7, VitA=469),
        "Carottes": _aliment(0.16, 41, 0.9, VitA=835, Potassium=320),
        "Parmesan": _aliment(2.80, 392, 35.8, Calcium=1180),
        "Kefir": _aliment(0.55, 55, 3.3, creami=1, Calcium=120, VitB12=0.4),
        "Fraises": _aliment(0.90, 32, 0.7, congelable=0, creami=1, VitC=59),
        "Proteine en poudre": _aliment(5.00, 373, 86.0, creami=1, minq=25,
                                       Calcium=550),
        "Creatine monohydrate": _aliment(6.00, 0, 0.0, creami=1, minq=5),
        "Farine tout usage": _aliment(0.11, 364, 10.3, minq=100),
        "Pates (sec)": _aliment(0.40, 359, 12.5, minq=125),
        "Kiwi": _aliment(1.29, 61, 0.9, congelable=0, creami=1, VitC=82),
    }
    df = pd.DataFrame.from_dict(data, orient="index")
    return df[_COLS]


@pytest.fixture
def cibles() -> dict[str, float]:
    return {
        "Calories": 2000.0, "Protéines": 120.0, "Lipides": 60.0,
        "Glucides": 220.0, "Poids_Corps": 60.0,
        "Calcium": 1000.0, "VitC": 90.0, "VitD": 15.0, "Fer": 8.0,
        "Potassium": 3400.0,
    }


# ── Construction du problème élargi ─────────────────────────────────────────

def test_le_bloc_taco_ne_retient_que_les_congelables(catalogue):
    noms = bc._bloc_autorise(catalogue, "taco")
    assert "Maquereau" in noms
    assert "Fraises" not in noms          # Congelable = 0


def test_le_bloc_creami_ne_retient_que_les_creami_ok(catalogue):
    noms = bc._bloc_autorise(catalogue, "creami")
    assert {"Kefir", "Fraises", "Proteine en poudre"} <= set(noms)
    assert "Maquereau" not in noms


def test_supplements_reserves_au_creami(catalogue):
    """Sans exclusivité, la poudre finit dans la garniture du taco."""
    assert "Proteine en poudre" not in bc._bloc_autorise(catalogue, "taco")
    assert "Creatine monohydrate" not in bc._bloc_autorise(catalogue, "frais")
    assert "Proteine en poudre" in bc._bloc_autorise(catalogue, "creami")


def test_matieres_premieres_et_pates_hors_recettes(catalogue):
    """La farine sert à chiffrer les tortillas, elle ne se mange pas telle quelle ;
    les pâtes ne se mettent pas dans une tortilla."""
    taco = bc._bloc_autorise(catalogue, "taco")
    assert "Farine tout usage" not in taco
    assert "Pates (sec)" not in taco
    assert "Farine tout usage" not in bc._bloc_autorise(catalogue, "frais")


def test_apports_multiplies_par_le_nombre_de_portions(catalogue):
    """Le taco compte double : une variable, deux portions par jour."""
    elargi = bc.construire_df_multibloc(catalogue)
    assert elargi.at["taco::Maquereau", "Energie"] == pytest.approx(205 * 2)
    assert elargi.at["taco::Maquereau", "Prix"] == pytest.approx(0.80 * 2)
    assert elargi.at["frais::Maquereau", "Energie"] == pytest.approx(205)


def test_les_imposes_sortent_du_probleme(catalogue):
    """Un ingrédient fixé ne doit pas redevenir variable de décision."""
    elargi = bc.construire_df_multibloc(
        catalogue, {"taco": {"Tortilla de mais": 30.0}, "creami": {}, "frais": {}})
    assert "taco::Tortilla de mais" not in elargi.index
    assert "frais::Tortilla de mais" in elargi.index


def test_plafond_sur_la_poudre_de_proteine(catalogue):
    elargi = bc.construire_df_multibloc(catalogue)
    assert elargi.at["creami::Proteine en poudre", "MaxQty"] == bc.MAX_PROTEINE_POUDRE_G


# ── Cibles résiduelles ──────────────────────────────────────────────────────

def test_les_imposes_sont_retranches_des_cibles(catalogue, cibles):
    """La créatine et la tortilla sont payées et comptées avant l'optimisation."""
    imposes = {"taco": {"Tortilla de mais": 30.0}, "creami": {}, "frais": {}}
    apport = bc._apport_impose(catalogue, imposes)
    # 30 g × 2 tacos = 60 g -> 0,6 × 218 kcal
    assert apport["Energie"] == pytest.approx(218 * 0.6)
    residuelles = bc._cibles_residuelles(cibles, apport)
    assert residuelles["Calories"] == pytest.approx(2000 - 218 * 0.6)
    assert residuelles["Poids_Corps"] == 60.0        # jamais touché


def test_les_cibles_residuelles_ne_passent_pas_sous_zero(catalogue, cibles):
    apport = {"Energie": 99_999.0}
    assert bc._cibles_residuelles(cibles, apport)["Calories"] == 0.0


# ── Structure imposée ───────────────────────────────────────────────────────

def _blocs(taco=None, creami=None):
    return {
        "taco": bc.BlocPlan("taco", 2, dict(taco or {})),
        "creami": bc.BlocPlan("creami", 1, dict(creami or {})),
        "frais": bc.BlocPlan("frais", 1, {}),
    }


def test_structure_complete_ne_signale_rien():
    blocs = _blocs(
        taco={"Tortilla de mais": 30, "Maquereau": 60, "Epinards": 40,
              "Carottes": 40, "Parmesan": 20},
        creami={"Kefir": 180, "Fraises": 120, "Proteine en poudre": 30,
                "Creatine monohydrate": 5},
    )
    assert bc.structure_respectee(blocs) == []


def test_une_portion_symbolique_ne_satisfait_pas_la_famille():
    """5 g de fraises « cochent » le fruit sans faire un dessert."""
    blocs = _blocs(
        taco={"Tortilla de mais": 30, "Maquereau": 60, "Epinards": 40,
              "Carottes": 40, "Parmesan": 20},
        creami={"Kefir": 5, "Fraises": 5, "Proteine en poudre": 30,
                "Creatine monohydrate": 5},
    )
    manques = bc.structure_respectee(blocs)
    assert any("base liquide" in m for m in manques)
    assert any("fruit" in m for m in manques)


def test_deux_tortillas_sont_refusees():
    blocs = _blocs(taco={"Tortilla de mais": 30, "Tortilla de ble": 45})
    assert any("exactement une tortilla" in m for m in bc.structure_respectee(blocs))


def test_un_seul_legume_ne_suffit_pas():
    blocs = _blocs(
        taco={"Tortilla de mais": 30, "Maquereau": 60, "Epinards": 40,
              "Parmesan": 20},
        creami={"Kefir": 180, "Fraises": 120, "Proteine en poudre": 30,
                "Creatine monohydrate": 5},
    )
    assert any("deux légumes" in m for m in bc.structure_respectee(blocs))


def test_creatine_absente_est_signalee():
    blocs = _blocs(
        taco={"Tortilla de mais": 30, "Maquereau": 60, "Epinards": 40,
              "Carottes": 40, "Parmesan": 20},
        creami={"Kefir": 180, "Fraises": 120, "Proteine en poudre": 30},
    )
    assert any("créatine" in m for m in bc.structure_respectee(blocs))


# ── Optimisation de bout en bout ────────────────────────────────────────────

@pytest.fixture(scope="module")
def journee(catalogue_module, cibles_module):
    return bc.optimiser_journee(catalogue_module, cibles_module,
                                budget_max_daily=25.0, seed=1,
                                tortilla="Tortilla de mais")


@pytest.fixture(scope="module")
def catalogue_module():
    data = {
        "Tortilla de mais": _aliment(0.30, 218, 5.7, minq=30, Calcium=81),
        "Maquereau": _aliment(0.80, 205, 19.0, VitD=8.0, Selenium=44),
        "Epinards": _aliment(0.50, 23, 2.9, VitC=28, Fer=2.7, VitA=469),
        "Carottes": _aliment(0.16, 41, 0.9, VitA=835, Potassium=320),
        "Parmesan": _aliment(2.80, 392, 35.8, Calcium=1180),
        "Kefir": _aliment(0.55, 55, 3.3, creami=1, Calcium=120, VitB12=0.4),
        "Fraises": _aliment(0.90, 32, 0.7, congelable=0, creami=1, VitC=59),
        "Proteine en poudre": _aliment(5.00, 373, 86.0, creami=1, minq=25,
                                       Calcium=550),
        "Creatine monohydrate": _aliment(6.00, 0, 0.0, creami=1, minq=5),
        "Kiwi": _aliment(1.29, 61, 0.9, congelable=0, creami=1, VitC=82),
    }
    df = pd.DataFrame.from_dict(data, orient="index")
    return df[_COLS]


@pytest.fixture(scope="module")
def cibles_module():
    return {
        "Calories": 2000.0, "Protéines": 120.0, "Lipides": 60.0,
        "Glucides": 220.0, "Poids_Corps": 60.0,
        "Calcium": 1000.0, "VitC": 90.0, "VitD": 15.0, "Fer": 8.0,
        "Potassium": 3400.0,
    }


def test_la_creatine_est_toujours_dosee(journee):
    """Elle n'apporte aucun nutriment : sans imposition, l'optimiseur l'écarte."""
    assert journee.creami.ingredients.get("Creatine monohydrate") == \
        bc.CREATINE_G_PAR_JOUR


def test_la_tortilla_est_presente_une_fois(journee):
    assert journee.taco.ingredients.get("Tortilla de mais", 0) > 0


def test_aucun_surplus_de_macros(journee, catalogue_module, cibles_module):
    """Test central du design : sur la journée complète `2 tacos + creami +
    frais`, les macros ne dépassent pas les cibles. Ce test doit échouer si l'on
    revient à une optimisation séquentielle (taco d'abord, complément ensuite).
    """
    totaux = {"Energie": 0.0, "Proteines": 0.0, "Lipides": 0.0, "Glucides": 0.0}
    for bloc in (journee.taco, journee.creami, journee.frais):
        for aliment, grammes in bloc.grammes_par_jour().items():
            if aliment not in catalogue_module.index:
                continue
            for col in totaux:
                totaux[col] += float(catalogue_module.at[aliment, col]) * grammes / 100.0

    # Même tolérance que l'optimiseur de fenêtre (les cibles sont des minimums
    # stricts sur calories/protéines, avec une marge haute admise).
    assert totaux["Energie"] <= cibles_module["Calories"] * 1.15
    assert totaux["Proteines"] <= cibles_module["Protéines"] * 1.35


def test_les_blocs_restent_separes(journee):
    """Aucun aliment non congelable dans le taco, aucun non-CREAMi dans le pot."""
    assert "Fraises" not in journee.taco.ingredients
    assert "Maquereau" not in journee.creami.ingredients


def test_grammes_par_jour_double_le_taco():
    bloc = bc.BlocPlan("taco", bc.TACOS_PAR_JOUR, {"Maquereau": 50.0})
    assert bloc.grammes_par_jour()["Maquereau"] == 100.0
