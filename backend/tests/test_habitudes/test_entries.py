from app.services.habitudes.entries import DEFAULT_HABITS


def test_default_habits_count():
    assert len(DEFAULT_HABITS) == 6


def test_default_habits_have_required_fields():
    for h in DEFAULT_HABITS:
        assert "nom" in h
        assert "type" in h
        assert h["type"] in ("binaire", "quantifiable")


def test_muscu_has_source_auto():
    muscu = next(h for h in DEFAULT_HABITS if h["nom"] == "Muscu")
    assert muscu["source_auto"] == "entrainement_muscu"


def test_lecture_is_quantifiable():
    lecture = next(h for h in DEFAULT_HABITS if h["nom"] == "Lecture")
    assert lecture["type"] == "quantifiable"
    assert lecture["cible"] == 30.0
