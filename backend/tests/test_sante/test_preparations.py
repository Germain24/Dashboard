"""Arbitrage cuisiner / acheter des préparations maison.

Le piège que ces tests verrouillent : comparer un prix au litre entre maison et
commerce alors que les deux produits n'ont pas la même densité nutritionnelle.
Le lait d'avoine du commerce est hydrolysé et additionné d'huile ; 90 g de
flocons ne peuvent pas en égaler l'apport. Une comparaison au volume concluait à
« 11× moins cher », la comparaison à apport équivalent conclut « acheter ».
"""
from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from app.services.sante import preparations as prep_mod
from app.services.sante.preparations import (
    PREPARATIONS,
    Preparation,
    appliquer_preparations_rentables,
    evaluer,
    evaluer_toutes,
    lot_minimal_rentable,
)


def _catalogue_test() -> pd.DataFrame:
    """Catalogue minimal : une matière première bon marché, un produit fini cher."""
    return pd.DataFrame(
        {
            "Prix": [0.10, 2.00],
            "Energie": [400.0, 40.0],
            "Proteines": [10.0, 1.0],
            "Lipides": [5.0, 1.0],
            "Glucides": [60.0, 6.0],
            "MinQty": [0.0, 0.0],
            "MaxQty": [0.0, 0.0],
            "Congelable": [1.0, 0.0],
            "CreamiOk": [1.0, 1.0],
        },
        index=["Matiere", "Produit commercial"],
    )


def _prep_test(**kwargs) -> Preparation:
    base = dict(
        nom="Preparation test",
        ingredients={"Matiere": 100.0},
        rendement_g=1000.0,
        equivalent_commercial="Produit commercial",
        temps_fixe_min=6.0,
        temps_variable_min=3.0,
        lot_defaut=1.0,
        extraction=1.0,
    )
    base.update(kwargs)
    return Preparation(**base)  # type: ignore[arg-type]


def test_profil_calcule_depuis_les_ingredients_et_le_rendement():
    df = _catalogue_test()
    # 100 g de matière à 400 kcal diluée dans 1000 g -> 40 kcal/100 g.
    ev = evaluer(_prep_test(), df)
    assert ev.profil["Energie"] == pytest.approx(40.0)
    assert ev.profil["Prix"] == pytest.approx(0.01)


def test_extraction_reduit_les_nutriments_mais_pas_le_prix():
    """L'okara jeté emporte des nutriments — la matière première, elle, est payée
    en entier. Confondre les deux surestime la rentabilité."""
    df = _catalogue_test()
    ev = evaluer(_prep_test(extraction=0.5), df)
    assert ev.profil["Energie"] == pytest.approx(20.0)   # moitié des nutriments
    assert ev.profil["Prix"] == pytest.approx(0.01)      # prix inchangé


def test_comparaison_a_apport_equivalent_et_non_au_volume():
    """Une préparation deux fois moins dense ne vaut que la moitié, à volume égal."""
    df = _catalogue_test()
    dense = evaluer(_prep_test(extraction=1.0), df)
    diluee = evaluer(_prep_test(extraction=0.5), df)
    assert dense.ratio_densite == pytest.approx(1.0)
    assert diluee.ratio_densite == pytest.approx(0.5)
    # Même coût de production, mais moitié moins de produit utile -> moitié moins
    # d'économie, donc un taux horaire strictement inférieur.
    assert diluee.taux_horaire < dense.taux_horaire


def test_verdict_suit_le_seuil_horaire():
    df = _catalogue_test()
    prep = _prep_test()
    ev_exigeant = evaluer(prep, df, taux_horaire=10_000.0)
    ev_permissif = evaluer(prep, df, taux_horaire=0.0)
    assert not ev_exigeant.rentable and "acheter" in ev_exigeant.motif
    assert ev_permissif.rentable


def test_le_verdict_suit_les_promotions():
    """Cœur du besoin : quand le produit commercial baisse, cuisiner cesse de
    valoir le coup — sans intervention."""
    df = _catalogue_test()
    prep = _prep_test()
    plein_tarif = evaluer(prep, df)
    df_promo = df.copy()
    df_promo.loc["Produit commercial", "Prix"] = 0.15
    en_promo = evaluer(prep, df_promo)
    assert en_promo.taux_horaire < plein_tarif.taux_horaire


def test_lot_minimal_rentable_exploite_le_temps_fixe():
    """Le temps de préparation étant surtout fixe, agrandir le lot améliore le
    taux horaire : un lot minimal doit exister sous un seuil atteignable."""
    df = _catalogue_test()
    prep = _prep_test(temps_fixe_min=30.0, temps_variable_min=1.0)
    petit = evaluer(prep, df, lot=1.0)
    grand = evaluer(prep, df, lot=8.0)
    assert grand.taux_horaire > petit.taux_horaire
    seuil = (petit.taux_horaire + grand.taux_horaire) / 2
    lot = lot_minimal_rentable(prep, df, taux_horaire=seuil)
    assert lot is not None and 1.0 < lot <= 8.0


def test_ingredient_absent_du_catalogue_ne_leve_pas():
    df = _catalogue_test()
    ev = evaluer(_prep_test(ingredients={"Introuvable": 100.0}), df)
    assert not ev.rentable
    assert ev.ingredients_manquants == ("Introuvable",)
    assert "absents du catalogue" in ev.motif


def test_seules_les_preparations_rentables_entrent_au_catalogue():
    """L'optimiseur ne doit jamais proposer de cuisiner à perte."""
    df = _catalogue_test()
    enrichi, _ = appliquer_preparations_rentables(df, taux_horaire=10_000.0)
    assert list(enrichi.index) == list(df.index)   # aucune retenue


def test_preparations_reelles_evaluables_sur_le_vrai_catalogue():
    """Chaque préparation déclarée doit pouvoir être chiffrée : un ingrédient
    absent du catalogue la rendrait muette au lieu de la juger."""
    from app.services.sante.aliments import load_aliments_dataframe

    df = load_aliments_dataframe()
    if df.empty:
        pytest.skip("catalogue indisponible")
    evaluations = evaluer_toutes(df)
    assert len(evaluations) == len(PREPARATIONS)
    for ev in evaluations:
        assert not ev.ingredients_manquants, f"{ev.nom}: {ev.ingredients_manquants}"
        assert ev.cout_par_100g > 0, ev.nom


def test_lait_avoine_reste_sous_le_seuil_meme_avec_une_extraction_parfaite():
    """Garde-fou contre le retour de l'erreur « 11× moins cher ».

    Même en supposant qu'aucun nutriment ne parte avec l'okara — impossible en
    pratique —, 90 g de flocons ne rattrapent pas la densité du produit
    hydrolysé du commerce, et le taux horaire reste sous 20 $/h.
    """
    from app.services.sante.aliments import load_aliments_dataframe

    df = load_aliments_dataframe()
    if df.empty:
        pytest.skip("catalogue indisponible")
    avoine = next(p for p in PREPARATIONS if "avoine" in p.nom)
    parfait = evaluer(dataclasses.replace(avoine, extraction=1.0), df)
    assert parfait.ratio_densite < 1.0
    assert not parfait.rentable, (
        f"rentabilité inattendue à extraction=1.0 ({parfait.taux_horaire:.2f} $/h) — "
        "vérifier la densité avant de conclure à une économie"
    )


def test_taux_horaire_par_defaut_est_la_regle_utilisateur():
    assert prep_mod.TAUX_HORAIRE_CAD == 20.0


def test_un_verdict_assis_sur_un_prix_estime_est_signale():
    """Les prix non relevés sur Super C doivent rester visibles : un arbitrage
    cuisiner/acheter fondé sur un prix inventé induirait en erreur."""
    from app.services.sante.aliments import load_aliments_dataframe

    df = load_aliments_dataframe()
    if df.empty:
        pytest.skip("catalogue indisponible")
    par_nom = {e.nom: e for e in evaluer_toutes(df)}

    tortilla = par_nom["Tortilla de mais maison"]
    assert not tortilla.verdict_fiable
    assert "Masa harina" in tortilla.prix_estimes
    assert "prix estimé" in tortilla.motif

    # Le lait d'avoine n'utilise que des aliments tarifés Super C.
    avoine = par_nom["Lait d'avoine maison"]
    assert avoine.verdict_fiable and not avoine.prix_estimes
