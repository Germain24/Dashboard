"""Fusion du réservoir généré avec le catalogue curé, au chargement."""
from __future__ import annotations

import pytest

from app.services.sante import aliments


def _ecrire_reservoir(path, lignes: list[str]) -> None:
    entete = "Aliment;Prix;Energie;Proteines;VitC;Source;UPC;Rayon;CiqualCode;CiqualNom;Confiance"
    path.write_text("\n".join([entete, *lignes]), encoding="utf-8")


@pytest.fixture
def reservoir(tmp_path, monkeypatch):
    chemin = tmp_path / "reservoir_superc.csv"
    monkeypatch.setattr(aliments, "_reservoir_path", lambda: chemin)
    return chemin


def test_reservoir_absent_ne_casse_rien(reservoir):
    """Le catalogue curé doit se charger même sans réservoir généré."""
    assert not reservoir.exists()
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    assert len(df) > 0


def test_reservoir_illisible_est_ignore_sans_lever(reservoir):
    reservoir.write_bytes(b"\xff\xfe pas du CSV \x00\x01")
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    assert len(df) > 0


def test_le_defaut_n_inclut_pas_le_reservoir(reservoir):
    """Défaut à False : aucun appelant existant ne change de comportement."""
    _ecrire_reservoir(reservoir, ["Produit Test;1;100;5;3;superc;1;boissons;1;Eau;0.9"])
    assert "Produit Test" not in aliments.load_aliments_dataframe().index
    assert "Produit Test" in aliments.load_aliments_dataframe(include_reservoir=True).index


def test_le_catalogue_cure_gagne_en_cas_d_homonymie(reservoir):
    """Une entrée vérifiée à la main l'emporte toujours sur un rattachement
    automatique — sinon le réservoir écraserait silencieusement un prix ou une
    teneur corrigés exprès."""
    cures = aliments.load_aliments_from_csv()
    nom = next(iter(cures))
    prix_cure = cures[nom]["Prix"]
    _ecrire_reservoir(reservoir, [f"{nom};999;1;1;1;superc;1;rayon;1;Faux;0.9"])
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    assert df.loc[nom, "Prix"] == pytest.approx(prix_cure)
    assert df.loc[nom, "Prix"] != 999


def test_les_colonnes_de_tracabilite_ne_polluent_pas_les_teneurs(reservoir):
    """`Source`, `UPC`, `Rayon` et `CiqualNom` sont du texte : les convertir en
    nombres créerait des colonnes numériques vides dans tout le catalogue."""
    _ecrire_reservoir(reservoir, ["Produit Test;1.5;100;5;3;superc;065;boissons;1;Eau;0.9"])
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    for colonne in ("Source", "UPC", "Rayon", "CiqualNom"):
        assert colonne not in df.columns
    assert df.loc["Produit Test", "Prix"] == pytest.approx(1.5)


def test_les_aliments_du_reservoir_ont_toutes_les_colonnes_requises(reservoir):
    """Une colonne manquante deviendrait 0.0 : l'aliment paraîtrait dépourvu du
    nutriment, ce qui est le sens voulu, mais la colonne doit exister."""
    _ecrire_reservoir(reservoir, ["Produit Test;1.5;100;5;3;superc;1;boissons;1;Eau;0.9"])
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    for colonne in aliments.REQUIRED_COLS:
        assert colonne in df.columns
    assert df.loc["Produit Test", "Iode"] == pytest.approx(0.0)


def test_rattachement_de_faible_confiance_est_exclu(reservoir):
    _ecrire_reservoir(reservoir, [
        "Pates aux oeufs;1.5;100;5;3;superc;123;garde-manger;1;Pate de fruits;0.3871"
    ])
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    assert "Pates aux oeufs" not in df.index
    assert "Pates aux oeufs" not in aliments.load_reservoir_product_refs()


def test_produit_ambigu_connu_est_redirige_au_lieu_d_etre_supprime(reservoir):
    _ecrire_reservoir(reservoir, [
        "Aurora Pâtes fettuccine aux œufs;1.5;100;5;3;superc;123;garde-manger;31014;Pâte de fruits;0.3871"
    ])
    aliments._ciqual_profile.cache_clear()
    df = aliments.load_aliments_dataframe(include_reservoir=True)
    assert "Aurora Pâtes fettuccine aux œufs" in df.index
    # Le faux profil fourni dans le réservoir (100 kcal) est remplacé par les
    # pâtes sèches aux œufs crues CIQUAL, mais le prix Super C est conservé.
    assert df.loc["Aurora Pâtes fettuccine aux œufs", "Energie"] != pytest.approx(100.0)
    assert df.loc["Aurora Pâtes fettuccine aux œufs", "Prix"] == pytest.approx(1.5)
    assert aliments.load_reservoir_product_refs()["Aurora Pâtes fettuccine aux œufs"] == "123"
    assert aliments.load_reservoir_ciqual_refs()["Aurora Pâtes fettuccine aux œufs"] == "9821"
