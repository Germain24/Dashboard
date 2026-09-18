"""Suivi de compétences (skill tree, niveaux + preuves) — #352."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.etudes import skills


# ── Fonctions pures ──────────────────────────────────────────────────────────

def test_skills_by_category_empty():
    assert skills.skills_by_category([]) == {}


def test_skills_by_category_groups_and_averages():
    data = [
        {"nom": "Python", "categorie": "technique", "niveau": 4},
        {"nom": "SQL", "categorie": "technique", "niveau": 2},
        {"nom": "Anglais", "categorie": "langue", "niveau": 5},
    ]
    result = skills.skills_by_category(data)
    assert result["technique"]["niveau_moyen"] == 3.0
    assert result["technique"]["nb_competences"] == 2
    assert result["technique"]["competences"] == ["Python", "SQL"]  # tri par niveau desc
    assert result["langue"]["niveau_moyen"] == 5.0
    assert result["langue"]["nb_competences"] == 1


def test_skills_by_category_rounds_to_one_decimal():
    data = [
        {"nom": "A", "categorie": "x", "niveau": 1},
        {"nom": "B", "categorie": "x", "niveau": 2},
        {"nom": "C", "categorie": "x", "niveau": 2},
    ]
    result = skills.skills_by_category(data)
    assert result["x"]["niveau_moyen"] == 1.7


def test_overall_stats_empty():
    stats = skills.overall_stats([])
    assert stats == {"nb_competences": 0, "niveau_moyen": 0.0, "nb_preuves_total": 0}


def test_overall_stats_computes():
    data = [
        {"nom": "A", "categorie": "x", "niveau": 3, "preuves": [{"date": "2026-01-01", "texte": "t"}]},
        {"nom": "B", "categorie": "x", "niveau": 5, "preuves": []},
    ]
    stats = skills.overall_stats(data)
    assert stats["nb_competences"] == 2
    assert stats["niveau_moyen"] == 4.0
    assert stats["nb_preuves_total"] == 1


# ── Fonctions avec store JSON ────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path):
    return tmp_path / "skills.json"


def test_list_empty(store):
    assert skills.list_skills(path=store) == []


def test_add_skill(store):
    skill = skills.add_skill("Python", "technique", 3, path=store, today=dt.date(2026, 7, 16))
    assert skill["nom"] == "Python"
    assert skill["categorie"] == "technique"
    assert skill["niveau"] == 3
    assert skill["preuves"] == []
    assert skill["cree_le"] == "2026-07-16"
    assert skill["id"] >= 1


def test_add_skill_default_niveau(store):
    skill = skills.add_skill("Guitare", "soft skill", path=store)
    assert skill["niveau"] == 1


def test_add_skill_invalid_niveau_too_low(store):
    with pytest.raises(ValueError):
        skills.add_skill("X", "technique", 0, path=store)


def test_add_skill_invalid_niveau_too_high(store):
    with pytest.raises(ValueError):
        skills.add_skill("X", "technique", 6, path=store)


def test_list_persists(store):
    skills.add_skill("Python", "technique", path=store)
    skills.add_skill("Anglais", "langue", path=store)
    result = skills.list_skills(path=store)
    assert len(result) == 2
    assert {s["nom"] for s in result} == {"Python", "Anglais"}


def test_update_skill(store):
    skill = skills.add_skill("Python", "technique", 2, path=store)
    updated = skills.update_skill(skill["id"], {"niveau": 4}, path=store)
    assert updated is not None
    assert updated["niveau"] == 4
    assert updated["nom"] == "Python"


def test_update_skill_invalid_niveau(store):
    skill = skills.add_skill("Python", "technique", 2, path=store)
    with pytest.raises(ValueError):
        skills.update_skill(skill["id"], {"niveau": 9}, path=store)


def test_update_skill_ignores_preuves(store):
    skill = skills.add_skill("Python", "technique", 2, path=store)
    updated = skills.update_skill(skill["id"], {"preuves": [{"date": "x", "texte": "y"}]}, path=store)
    assert updated["preuves"] == []


def test_update_nonexistent(store):
    assert skills.update_skill(999, {"niveau": 3}, path=store) is None


def test_remove_skill(store):
    skill = skills.add_skill("Python", "technique", path=store)
    assert skills.remove_skill(skill["id"], path=store) is True
    assert skills.list_skills(path=store) == []


def test_remove_nonexistent(store):
    assert skills.remove_skill(999, path=store) is False


def test_add_preuve_existing(store):
    skill = skills.add_skill("Python", "technique", path=store)
    result = skills.add_preuve(skill["id"], "Terminé le cours X", date="2026-07-10", path=store)
    assert result is not None
    assert result["preuves"] == [{"date": "2026-07-10", "texte": "Terminé le cours X"}]


def test_add_preuve_default_date(store):
    skill = skills.add_skill("Python", "technique", path=store)
    result = skills.add_preuve(skill["id"], "Projet livré", path=store)
    assert result["preuves"][0]["date"] == dt.date.today().isoformat()


def test_add_preuve_most_recent_first(store):
    skill = skills.add_skill("Python", "technique", path=store)
    skills.add_preuve(skill["id"], "Ancienne preuve", date="2026-01-01", path=store)
    result = skills.add_preuve(skill["id"], "Nouvelle preuve", date="2026-07-16", path=store)
    assert result["preuves"][0]["texte"] == "Nouvelle preuve"
    assert result["preuves"][1]["texte"] == "Ancienne preuve"


def test_add_preuve_nonexistent(store):
    assert skills.add_preuve(999, "texte", path=store) is None
