"""Modèles LieuVoyage."""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401 — enregistre toutes les tables
from app.models.voyage import LieuVoyage


def _mem_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_lieu_voyage_roundtrip():
    with _mem_session() as s:
        lv = LieuVoyage(
            nom="Table Mountain", ville="Le Cap", pays="Afrique du Sud", visite=False,
            aeroport_iata="CPT", jours_min=2, jours_max=4, cout_jour_estime=80.0,
        )
        s.add(lv)
        s.commit()
        s.refresh(lv)
        got = s.get(LieuVoyage, lv.id)
        assert got is not None
        assert got.nom == "Table Mountain"
        assert got.cout_jour_estime == 80.0


def test_lieu_voyage_defaults():
    with _mem_session() as s:
        lv = LieuVoyage(nom="K-2")
        s.add(lv)
        s.commit()
        s.refresh(lv)
        assert lv.visite is False
        assert lv.ville is None
        assert lv.aeroport_iata is None
