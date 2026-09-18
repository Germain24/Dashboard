"""Traduction CIQUAL 2020 -> colonnes du dépôt (logique pure, sans I/O)."""
from __future__ import annotations

import pytest

from app.services.sante import ciqual
from app.services.sante.aliments import REQUIRED_COLS


class TestParseValue:
    """Les quatre formes réellement présentes dans la table ANSES."""

    def test_nombre_a_virgule_decimale(self):
        assert ciqual.parse_value("21,6") == pytest.approx(21.6)

    def test_separateur_de_milliers(self):
        assert ciqual.parse_value("1 234,5") == pytest.approx(1234.5)
        assert ciqual.parse_value("1 234,5") == pytest.approx(1234.5)  # insécable

    def test_tiret_signifie_inconnu_pas_zero(self):
        """Distinction essentielle : « - » = non déterminé. Le confondre avec 0
        reviendrait à affirmer une absence qui n'a jamais été mesurée."""
        assert ciqual.parse_value("-") is None
        assert ciqual.parse_value("") is None
        assert ciqual.parse_value(None) is None

    def test_traces_valent_zero(self):
        assert ciqual.parse_value("traces") == 0.0
        assert ciqual.parse_value("Traces") == 0.0

    def test_inferieur_a_un_seuil_prend_le_milieu(self):
        assert ciqual.parse_value("< 0,5") == pytest.approx(0.25)
        assert ciqual.parse_value("<2") == pytest.approx(1.0)

    def test_texte_non_chiffrable_reste_inconnu(self):
        assert ciqual.parse_value("n.d.") is None


class TestConvertRow:
    def test_les_teneurs_inconnues_sont_omises_et_non_mises_a_zero(self):
        out = ciqual.convert_row({"Vitamine C (mg/100 g)": "-", "Lipides (g/100 g)": "3"})
        assert "VitC" not in out
        assert out["Lipides"] == pytest.approx(3.0)

    def test_omega3_somme_ala_epa_dha(self):
        out = ciqual.convert_row({
            "AG 18:3 c9,c12,c15 (n-3), alpha-linolénique (g/100 g)": "1,0",
            "AG 20:5 5c,8c,11c,14c,17c (n-3) EPA (g/100 g)": "0,5",
            "AG 22:6 4c,7c,10c,13c,16c,19c (n-3) DHA (g/100 g)": "0,25",
        })
        assert out["Omega 3"] == pytest.approx(1.75)

    def test_une_somme_ignore_les_composants_inconnus_mais_garde_les_autres(self):
        """Un EPA non déterminé ne doit pas faire perdre l'ALA, qui est mesuré."""
        out = ciqual.convert_row({
            "AG 18:3 c9,c12,c15 (n-3), alpha-linolénique (g/100 g)": "2,0",
            "AG 20:5 5c,8c,11c,14c,17c (n-3) EPA (g/100 g)": "-",
            "AG 22:6 4c,7c,10c,13c,16c,19c (n-3) DHA (g/100 g)": "-",
        })
        assert out["Omega 3"] == pytest.approx(2.0)

    def test_vitk_somme_k1_et_k2(self):
        out = ciqual.convert_row({
            "Vitamine K1 (µg/100 g)": "80", "Vitamine K2 (µg/100 g)": "40",
        })
        assert out["VitK"] == pytest.approx(120.0)

    def test_vitamine_a_convertit_le_betacarotene_en_equivalent_retinol(self):
        """12 µg de bêta-carotène = 1 µg de rétinol. Additionner les µg bruts
        surestimerait massivement la vitamine A des légumes orange."""
        out = ciqual.convert_row({
            "Rétinol (µg/100 g)": "100", "Beta-Carotène (µg/100 g)": "1200",
        })
        assert out["VitA"] == pytest.approx(200.0)  # 100 + 1200/12

    def test_proteines_repli_sur_facteur_625(self):
        out = ciqual.convert_row({
            "Protéines, N x facteur de Jones (g/100 g)": "-",
            "Protéines, N x 6.25 (g/100 g)": "12,5",
        })
        assert out["Proteines"] == pytest.approx(12.5)


class TestEnergieDerivee:
    def test_energie_tabulee_est_prioritaire(self):
        out = ciqual.convert_row({
            "Energie, Règlement UE N° 1169/2011 (kcal/100 g)": "250",
            "Protéines, N x facteur de Jones (g/100 g)": "10",
            "Lipides (g/100 g)": "10",
            "Glucides (g/100 g)": "10",
        })
        assert out["Energie"] == pytest.approx(250.0)

    def test_energie_derivee_des_macros_quand_absente(self):
        """888 aliments CIQUAL (plats composés) n'ont aucune énergie tabulée mais
        ont bien leurs macros. Sans ce calcul ils entreraient à 0 kcal, et
        l'optimiseur les verrait comme des micronutriments gratuits."""
        out = ciqual.convert_row({
            "Energie, Règlement UE N° 1169/2011 (kcal/100 g)": "-",
            "Protéines, N x facteur de Jones (g/100 g)": "10",   # 40 kcal
            "Lipides (g/100 g)": "5",                             # 45 kcal
            "Glucides (g/100 g)": "20",                           # 80 kcal
            "Fibres alimentaires (g/100 g)": "3",                 #  6 kcal
        })
        assert out["Energie"] == pytest.approx(171.0)

    def test_alcool_et_acides_organiques_comptent(self):
        out = ciqual.convert_row({
            "Energie, Règlement UE N° 1169/2011 (kcal/100 g)": "-",
            "Glucides (g/100 g)": "0",
            "Protéines, N x facteur de Jones (g/100 g)": "0",
            "Lipides (g/100 g)": "0",
            "Alcool (g/100 g)": "10",             # 70 kcal
            "Acides organiques (g/100 g)": "1",   #  3 kcal
        })
        assert out["Energie"] == pytest.approx(73.0)

    def test_aucune_macro_connue_ne_produit_aucune_energie_inventee(self):
        out = ciqual.convert_row({
            "Energie, Règlement UE N° 1169/2011 (kcal/100 g)": "-",
            "Protéines, N x facteur de Jones (g/100 g)": "-",
            "Lipides (g/100 g)": "-",
            "Glucides (g/100 g)": "-",
            "Calcium (mg/100 g)": "120",
        })
        assert "Energie" not in out


def test_toutes_les_colonnes_produites_existent_dans_le_catalogue():
    """Garde-fou : une colonne mal nommée ici resterait à zéro dans le catalogue
    sans qu'aucune erreur ne soit levée.

    La référence est l'union de `REQUIRED_COLS` et des propriétés réellement
    présentes dans `aliments.csv` — le catalogue porte des colonnes en surplus
    légitimes (`Amidon`, par exemple) que le loader conserve telles quelles.
    """
    from app.services.sante.aliments import load_aliments_from_csv

    catalogue = load_aliments_from_csv()
    proprietes = set(REQUIRED_COLS)
    if catalogue:
        proprietes |= set(next(iter(catalogue.values())))

    produites = set(ciqual.SIMPLE_MAP) | set(ciqual.SUM_MAP) | {"VitA"}
    inconnues = produites - proprietes
    assert not inconnues, f"colonnes inconnues du catalogue : {sorted(inconnues)}"


def test_les_micros_cibles_sont_tous_couverts():
    """Chaque micronutriment que l'optimiseur cherche à couvrir doit pouvoir
    être renseigné depuis CIQUAL, sinon le rattachement serait aveugle dessus."""
    from app.services.sante.constants import DAILY_BASE_TARGETS_NUTRIENTS, NUTRIENT_KEY_TO_CSV

    produites = set(ciqual.SIMPLE_MAP) | set(ciqual.SUM_MAP) | {"VitA"}
    manquants = []
    for key in DAILY_BASE_TARGETS_NUTRIENTS:
        csv_col = NUTRIENT_KEY_TO_CSV.get(key)
        # TotalSugars est dérivé par le loader depuis les composants sucrés.
        if csv_col in (None, "TotalSugars"):
            continue
        if csv_col not in produites:
            manquants.append(csv_col)
    assert not manquants, f"micros non alimentables depuis CIQUAL : {manquants}"


def test_identity_extrait_code_nom_et_groupes():
    ident = ciqual.identity({
        "alim_code": "13000", "alim_nom_fr": " Pomme crue ",
        "alim_grp_nom_fr": "fruits", "alim_ssgrp_nom_fr": "fruits frais",
    })
    assert ident == {
        "CiqualCode": "13000", "CiqualNom": "Pomme crue",
        "CiqualGroupe": "fruits", "CiqualSousGroupe": "fruits frais",
    }
