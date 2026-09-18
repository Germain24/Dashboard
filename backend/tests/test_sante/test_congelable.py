"""Garde-fous sur les propriétés d'usage du catalogue (`Congelable`, `CreamiOk`).

Le batch cooking filtre sur ces colonnes : une valeur manquante devient
silencieusement 0.0 (le loader comble les trous), ce qui exclurait un aliment
sans que personne s'en aperçoive. D'où ces vérifications sur le vrai CSV.
"""
from __future__ import annotations

import pytest

from app.services.sante.aliments import load_aliments_dataframe


@pytest.fixture(scope="module")
def catalogue():
    df = load_aliments_dataframe()
    if df.empty:
        pytest.skip("catalogue aliments indisponible")
    return df


def test_propriete_congelable_presente_et_binaire(catalogue):
    assert "Congelable" in catalogue.columns
    valeurs = set(catalogue["Congelable"].unique().tolist())
    assert valeurs <= {0.0, 1.0}, f"valeurs inattendues : {valeurs - {0.0, 1.0}}"


def test_les_deux_familles_sont_representees(catalogue):
    """Ni tout à 1 (ligne oubliée) ni tout à 0 (inversion de la logique)."""
    congelables = int(catalogue["Congelable"].sum())
    assert 0 < congelables < len(catalogue)


def test_cas_connus(catalogue):
    """Quelques ancrages : un cru aqueux, un laitage frais, une viande, une tortilla."""
    attendus = {
        "Concombre": 0.0,          # cru gorgé d'eau
        "Yogourt grec nature 0%": 0.0,  # émulsion qui graine
        "Poitrine de poulet": 1.0,
        "Tortilla de mais": 1.0,
        "Tortilla de ble": 1.0,
    }
    for nom, attendu in attendus.items():
        assert nom in catalogue.index, f"{nom} absent du catalogue"
        assert catalogue.loc[nom, "Congelable"] == attendu, nom


def test_tortillas_ont_les_champs_indispensables(catalogue):
    """Une tortilla sans Energie ni Prix fausserait toute l'optimisation."""
    for nom in ("Tortilla de mais", "Tortilla de ble"):
        row = catalogue.loc[nom]
        for champ in ("Prix", "Energie", "Proteines", "Glucides", "Lipides", "MinQty"):
            assert float(row[champ]) > 0, f"{nom}.{champ} vaut 0"


def test_creami_est_binaire_et_non_vide(catalogue):
    assert "CreamiOk" in catalogue.columns
    assert set(catalogue["CreamiOk"].unique().tolist()) <= {0.0, 1.0}
    assert 0 < int(catalogue["CreamiOk"].sum()) < len(catalogue)


def test_creami_et_congelable_sont_des_criteres_distincts(catalogue):
    """La CREAMi rabote un bloc congelé : l'éclatement des cellules par le gel y
    est recherché, pas subi. Des aliments impropres au plat cuisiné congelé (fruits
    crus, laitages) doivent donc être à CreamiOk=1 — sinon les deux colonnes
    encodent la même chose et la seconde ne sert à rien."""
    ni_l_un_ni_l_autre = catalogue[
        (catalogue["Congelable"] == 0) & (catalogue["CreamiOk"] == 1)
    ]
    assert len(ni_l_un_ni_l_autre) >= 10, (
        "trop peu d'aliments rattrapés par la CREAMi — critère probablement recopié"
    )
    for nom in ("Banane", "Yogourt grec nature 0%", "Fraises"):
        assert catalogue.loc[nom, "CreamiOk"] == 1.0, nom
    # À l'inverse, une viande n'a rien à faire en dessert glacé.
    assert catalogue.loc["Poitrine de poulet", "CreamiOk"] == 0.0


def test_matieres_premieres_des_preparations_presentes(catalogue):
    """Farine et masa harina servent à chiffrer les tortillas maison : absentes,
    l'arbitrage cuisiner/acheter ne peut pas se calculer."""
    for nom in ("Farine tout usage", "Masa harina"):
        assert nom in catalogue.index, f"{nom} absent du catalogue"
        for champ in ("Prix", "Energie", "Proteines", "Glucides"):
            assert float(catalogue.loc[nom, champ]) > 0, f"{nom}.{champ} vaut 0"


def test_pas_de_preparation_maison_figee_dans_le_csv(catalogue):
    """Les préparations maison sont CALCULÉES depuis leurs ingrédients
    (`preparations.py`) pour suivre les promotions. Une colonne figée dans le CSV
    reviendrait à un prix périmé, et masquerait la différence de densité
    nutritionnelle avec le produit du commerce."""
    figees = [n for n in catalogue.index if "maison" in n.lower()]
    assert not figees, f"préparations figées dans le CSV : {figees}"
