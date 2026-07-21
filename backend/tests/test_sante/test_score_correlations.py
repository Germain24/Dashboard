"""Corrélations du score de forme (§5.2 de la feuille de route P2).

Le score est calculé à partir de sommeil + sport + nutrition : le corréler à ces
trois-là ne dirait rien (une variable contre ses propres entrées). On le corrèle
donc à des signaux qui n'entrent PAS dans son calcul — humeur, énergie, poids —
ce qui est la seule question qui ait un sens : « mes bonnes journées de forme
tombent-elles avec ma bonne humeur / mon poids ? »

Réutilise `correlate_series` du module journal (déjà testé) plutôt que de
recalculer un Pearson.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_humeur_et_poids(session, jours: int = 20):
    """Humeur qui monte, poids qui descend, sur des dates consécutives."""
    from app.models.journal import MoodEntry
    from app.models.sante import MesureSante

    today = dt.date.today()
    for k in range(jours):
        d = today - dt.timedelta(days=k)
        session.add(MoodEntry(date=d, humeur=1 + (k % 5), energie=1 + (k % 5)))
        session.add(MesureSante(date=d, poids=57.0 + k * 0.1))
    session.commit()


def test_score_correlations_shape(session):
    """Contrat identique aux corrélations du journal (caveat + liste)."""
    from app.services.sante.score_correlations import score_correlations

    _seed_humeur_et_poids(session)
    out = score_correlations(session, jours=20)

    assert "corrélation" in out["caveat"].lower()
    assert out["jours"] == 20
    cibles = {c["cible"] for c in out["correlations"]}
    assert {"humeur", "energie", "poids"} <= cibles
    for c in out["correlations"]:
        assert c["source"] == "score"
        assert set(c) >= {"source", "cible", "r", "n"}


def test_score_correlations_exclut_ses_composantes(session):
    """Ni sommeil, ni sport, ni nutrition : ce sont les entrées du score."""
    from app.services.sante.score_correlations import score_correlations

    _seed_humeur_et_poids(session)
    cibles = {c["cible"] for c in score_correlations(session, jours=20)["correlations"]}

    assert not ({"sommeil", "sport", "nutrition"} & cibles)


def test_score_correlations_sans_donnees(session):
    """Base vide : r indéterminé, aucune exception."""
    from app.services.sante.score_correlations import score_correlations

    out = score_correlations(session, jours=10)

    assert out["correlations"]
    assert all(c["r"] is None for c in out["correlations"])
