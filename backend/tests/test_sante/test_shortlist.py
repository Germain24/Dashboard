"""Présélection des aliments soumis à l'optimiseur."""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.sante.shortlist import build_shortlist

TARGETS = {"VitC": 100.0, "Fer": 13.0, "Iode": 150.0, "Calcium": 1000.0,
           "Sodium_Max": 2000.0, "Calories": 2000.0, "Protéines": 120.0}


def _df(n: int, **surcharges) -> pd.DataFrame:
    """Catalogue synthétique : `n` aliments quelconques, plus des cas nommés."""
    data = {
        f"Aliment{i}": {
            "Prix": 1.0 + i * 0.01, "VitC": i % 7, "Fer": i % 5, "Iode": 0.0,
            "Calcium": i % 11, "Sodium": 500.0, "Energie": 100.0, "Proteines": 5.0,
        }
        for i in range(n)
    }
    data.update(surcharges)
    return pd.DataFrame.from_dict(data, orient="index")


def test_catalogue_plus_petit_que_le_plafond_est_rendu_tel_quel():
    df = _df(50)
    assert build_shortlist(df, TARGETS, n_max=400).equals(df)


def test_le_plafond_est_respecte():
    assert len(build_shortlist(_df(1000), TARGETS, n_max=400)) == 400


def test_les_aliments_proteges_survivent_toujours():
    """Un aliment curé, en stock ou favori ne doit jamais être évincé, même s'il
    est mauvais en densité par dollar : l'écarter ferait racheter du stock déjà
    possédé, ou perdrait une saisie vérifiée à la main."""
    df = _df(1000, Pitoyable={"Prix": 99.0, "VitC": 0.0, "Fer": 0.0, "Iode": 0.0,
                              "Calcium": 0.0, "Sodium": 0.0, "Energie": 1.0,
                              "Proteines": 0.0})
    out = build_shortlist(df, TARGETS, n_max=50, keep_names=frozenset({"Pitoyable"}))
    assert "Pitoyable" in out.index


def test_les_proteges_au_dela_du_plafond_sont_tous_gardes():
    """Mieux vaut une optimisation lente qu'un plan amputé du garde-manger."""
    df = _df(300)
    proteges = frozenset(f"Aliment{i}" for i in range(120))
    out = build_shortlist(df, TARGETS, n_max=50, keep_names=proteges)
    assert proteges <= set(out.index)


def test_un_porteur_de_chaque_nutriment_est_conserve():
    """L'unique source d'iode doit survivre au tri, même chère : sans elle le
    nutriment devient impossible à couvrir, quel que soit le reste du panier."""
    df = _df(1000, SeulPorteurIode={"Prix": 40.0, "VitC": 0.0, "Fer": 0.0,
                                    "Iode": 900.0, "Calcium": 0.0,
                                    "Sodium": 0.0, "Energie": 50.0, "Proteines": 0.0})
    out = build_shortlist(df, TARGETS, n_max=100)
    assert "SeulPorteurIode" in out.index


def test_les_nutriments_plafonds_ne_tirent_pas_la_selection():
    """Sodium, sucres, gras saturés et cholestérol sont des LIMITES. Un aliment
    qui n'a pour lui que d'être très salé par dollar ne doit pas être promu."""
    df = _df(1000, BombeDeSel={"Prix": 0.02, "VitC": 0.0, "Fer": 0.0, "Iode": 0.0,
                               "Calcium": 0.0, "Sodium": 90000.0, "Energie": 0.0,
                               "Proteines": 0.0})
    out = build_shortlist(df, TARGETS, n_max=100)
    assert "BombeDeSel" not in out.index


def test_un_prix_nul_ne_donne_pas_une_densite_infinie():
    """Une donnée de prix manquante (0) rendrait la densité infinie et l'aliment
    imbattable — il raflerait toutes les places du tri."""
    df = _df(1000, PrixManquant={"Prix": 0.0, "VitC": 1.0, "Fer": 1.0, "Iode": 0.0,
                                 "Calcium": 1.0, "Sodium": 0.0, "Energie": 10.0,
                                 "Proteines": 1.0})
    out = build_shortlist(df, TARGETS, n_max=100)
    assert len(out) == 100  # pas d'explosion, sélection normale


def test_sortie_deterministe_et_dans_l_ordre_du_catalogue():
    df = _df(1000)
    a = build_shortlist(df, TARGETS, n_max=200)
    b = build_shortlist(df, TARGETS, n_max=200)
    assert list(a.index) == list(b.index)
    positions = [list(df.index).index(n) for n in a.index]
    assert positions == sorted(positions)


def test_sans_cible_exploitable_on_tronque_sans_inventer_de_critere():
    df = _df(500)
    out = build_shortlist(df, {"CibleInconnue": 1.0}, n_max=100,
                          keep_names=frozenset({"Aliment499"}))
    assert len(out) == 100
    assert "Aliment499" in out.index


def test_les_teneurs_ne_sont_pas_modifiees():
    df = _df(600)
    out = build_shortlist(df, TARGETS, n_max=200)
    for nom in out.index:
        assert out.loc[nom, "VitC"] == pytest.approx(df.loc[nom, "VitC"])
        assert out.loc[nom, "Prix"] == pytest.approx(df.loc[nom, "Prix"])
