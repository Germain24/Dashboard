from app.services.musique.constants import (
    AMBIANCE_NAMES, AMBIANCE_LABELS, AMBIANCES, LABEL_TO_SLUG,
)


def test_catalogue_a_huit_playlists():
    assert len(AMBIANCE_NAMES) == 8


def test_slugs_sont_ascii_sans_slash_ni_espace():
    for slug in AMBIANCE_NAMES:
        assert slug.isascii(), slug
        assert "/" not in slug and " " not in slug, slug


def test_bijection_slug_label():
    assert set(AMBIANCE_LABELS) == set(AMBIANCE_NAMES)
    assert set(AMBIANCES) == set(AMBIANCE_NAMES)
    assert set(LABEL_TO_SLUG.values()) == set(AMBIANCE_NAMES)
    assert len(LABEL_TO_SLUG) == 8


def test_quelques_correspondances():
    assert AMBIANCE_LABELS["amour-love-sex"] == "amour/love/sex"
    assert AMBIANCE_LABELS["cafe-petit-dej"] == "café pour le petit dep"
    assert LABEL_TO_SLUG["Mélancolie"] == "melancolie"
