"""Rabais étudiant Super C (10 %, lundi→mercredi)."""
import datetime as dt

import pytest

from app.services.cuisine import student_discount

LUNDI = dt.date(2026, 7, 20)


@pytest.mark.parametrize("offset,attendu", [
    (0, True),    # lundi
    (1, True),    # mardi
    (2, True),    # mercredi
    (3, False),   # jeudi
    (4, False),   # vendredi
    (5, False),   # samedi
    (6, False),   # dimanche
])
def test_applies_on_couvre_lundi_a_mercredi(offset, attendu):
    assert student_discount.applies_on(LUNDI + dt.timedelta(days=offset)) is attendu


def test_sans_jour_connu_aucun_rabais_suppose():
    """On ne suppose jamais un rabais qu'on ne peut pas justifier : sous-estimer
    la facture serait pire que de la surestimer."""
    assert student_discount.applies_on(None) is False
    assert student_discount.factor(None) == 1.0
    assert student_discount.apply(10.0, None) == 10.0


def test_apply_retire_dix_pourcent_un_jour_eligible():
    assert student_discount.apply(10.0, LUNDI) == pytest.approx(9.0)
    assert student_discount.apply(2.49, LUNDI) == pytest.approx(2.241)


def test_apply_laisse_intact_un_jour_non_eligible():
    assert student_discount.apply(10.0, LUNDI + dt.timedelta(days=3)) == 10.0


def test_apply_tolere_les_valeurs_non_chiffrables():
    """Contrat best-effort du pipeline prix : jamais d'exception."""
    assert student_discount.apply(None, LUNDI) is None
    assert student_discount.apply("", LUNDI) == ""
    assert student_discount.apply(0.0, LUNDI) == 0.0


def test_desactivable_par_variable_d_environnement(monkeypatch):
    monkeypatch.setenv("STUDENT_DISCOUNT", "0")
    assert student_discount.applies_on(LUNDI) is False
    assert student_discount.apply(10.0, LUNDI) == 10.0


def test_le_rabais_uniforme_ne_change_aucun_classement():
    """Garde-fou contre une attente fausse : un facteur uniforme préserve
    l'ordre couverture/coût, donc l'optimiseur choisira exactement la même
    chose. Le gain est comptable, pas qualitatif."""
    prix = [1.20, 3.50, 0.80, 7.10]
    remises = [student_discount.apply(p, LUNDI) for p in prix]
    assert sorted(range(len(prix)), key=prix.__getitem__) == \
        sorted(range(len(remises)), key=remises.__getitem__)
    ratios = [r / p for r, p in zip(remises, prix)]
    assert all(r == pytest.approx(0.9) for r in ratios)
