"""Photos de vêtements (#75)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.garderobe import Vetement
from app.services.garderobe.photos import save_vetement_photo


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _add(session, vid="pull-marine", couleur=None):
    v = Vetement(id=vid, nom="Pull", categorie="Pull", couleur=couleur)
    session.add(v)
    session.commit()
    return v


def test_save_sets_photo_url(session, tmp_path):
    _add(session)
    v = save_vetement_photo(session, "pull-marine", "p.JPG", b"bytes", base_dir=tmp_path)
    assert v.extra["photo_url"] == "/media/garderobe/pull-marine.jpg"
    assert (tmp_path / "pull-marine.jpg").exists()


def test_dominant_color_fills_empty_couleur(session, tmp_path):
    _add(session, couleur=None)
    v = save_vetement_photo(session, "pull-marine", "p.jpg", b"x", couleur_dominante="#1b2a4a", base_dir=tmp_path)
    assert v.couleur == "#1b2a4a"
    assert v.extra["couleur_dominante"] == "#1b2a4a"


def test_dominant_color_does_not_override_existing(session, tmp_path):
    _add(session, couleur="Bleu Marine")
    v = save_vetement_photo(session, "pull-marine", "p.jpg", b"x", couleur_dominante="#1b2a4a", base_dir=tmp_path)
    assert v.couleur == "Bleu Marine"  # couleur existante préservée
    assert v.extra["couleur_dominante"] == "#1b2a4a"


def test_unknown_vetement_raises(session, tmp_path):
    with pytest.raises(KeyError):
        save_vetement_photo(session, "inconnu", "p.jpg", b"x", base_dir=tmp_path)


def test_id_is_sanitized(session, tmp_path):
    v = Vetement(id="t/shirt blanc", nom="T", categorie="Haut")
    session.add(v)
    session.commit()
    out = save_vetement_photo(session, "t/shirt blanc", "p.png", b"x", base_dir=tmp_path)
    assert out.extra["photo_url"] == "/media/garderobe/t_shirt_blanc.png"
