import datetime as dt
from app.models.skincare import SkincareProduct
from app.services.skincare.frequency import is_due_on, is_flexible

# 2026-06-01 est un lundi (weekday 0), 2026-06-04 est un jeudi (weekday 3)
LUNDI = dt.date(2026, 6, 1)
MARDI = dt.date(2026, 6, 2)
JEUDI = dt.date(2026, 6, 4)


def test_quotidien_due_every_day():
    p = SkincareProduct(nom="x", frequence_type="quotidien")
    assert is_due_on(p, LUNDI) is True
    assert is_due_on(p, MARDI) is True


def test_hebdo_jours_matches_weekday():
    p = SkincareProduct(nom="x", frequence_type="hebdo_jours", frequence_jours="0,3")
    assert is_due_on(p, LUNDI) is True   # lundi = 0
    assert is_due_on(p, MARDI) is False  # mardi = 1
    assert is_due_on(p, JEUDI) is True   # jeudi = 3


def test_n_par_semaine_is_flexible_not_due_specific_day():
    p = SkincareProduct(nom="x", frequence_type="n_par_semaine", frequence_n=2)
    assert is_due_on(p, LUNDI) is False
    assert is_flexible(p) is True


def test_quotidien_not_flexible():
    p = SkincareProduct(nom="x", frequence_type="quotidien")
    assert is_flexible(p) is False
