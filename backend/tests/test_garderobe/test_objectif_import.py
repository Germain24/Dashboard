"""Modèle ObjectifType + colonne Vetement.type_objectif."""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401 — enregistre toutes les tables
from app.models.garderobe import ObjectifType, Vetement


def _mem_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_objectif_type_roundtrip():
    with _mem_session() as s:
        s.add(ObjectifType(nom="T-shirts", ordre=0, quantite_objectif=15,
                            echelle=["Uniqlo U", "Visvim"]))
        s.commit()
        got = s.get(ObjectifType, "T-shirts")
        assert got is not None
        assert got.quantite_objectif == 15
        assert got.echelle == ["Uniqlo U", "Visvim"]


def test_vetement_has_type_objectif():
    with _mem_session() as s:
        s.add(Vetement(id="v1", nom="Tee", categorie="Haut", type_objectif="T-shirts"))
        s.commit()
        assert s.get(Vetement, "v1").type_objectif == "T-shirts"
