"""Projection d'épargne à intérêts composés."""

from app.services.finance.projection import project_savings, mois_pour_objectif


def test_no_growth_is_sum_of_contributions():
    r = project_savings(initial=1000, versement_mensuel=100, taux_annuel_pct=0, mois=12)
    assert r["valeur_finale"] == 1000 + 100 * 12  # 2200
    assert r["total_verse"] == 2200
    assert r["total_interets"] == 0.0
    assert len(r["courbe"]) == 13  # mois 0..12


def test_growth_adds_interest():
    r = project_savings(initial=1000, versement_mensuel=0, taux_annuel_pct=12, mois=12)
    # 1000 capitalisé à 1%/mois sur 12 mois ≈ 1126.83
    assert r["valeur_finale"] > 1120
    assert r["total_verse"] == 1000
    assert r["total_interets"] > 0


def test_mois_pour_objectif():
    # déjà atteint
    assert mois_pour_objectif(1000, 100, 0, 500) == 0
    # 0 + 100/mois sans intérêt -> 10 mois pour 1000
    assert mois_pour_objectif(0, 100, 0, 1000) == 10
    # hors d'atteinte
    assert mois_pour_objectif(0, 0, 0, 1000, max_mois=12) is None
