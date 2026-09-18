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


import openpyxl  # noqa: E402
from app.services.garderobe.objectif_import import parse_objectif_xlsx, sync_objectif  # noqa: E402


def _make_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, "Quantité objectif", "Qualité/Prix", "Qualité 1", "Qualité 2"])
    ws.append(["T-shirts", 2, "Uniqlo U", "Beams Plus", "Visvim"])
    ws.append(["Polos", 1, "Uniqlo", "Uniqlo", None])  # doublon → dédup
    ws.append([None, None, None, None, None])           # ligne vide → ignorée
    wb.save(path)


def test_parse_objectif_xlsx(tmp_path):
    p = tmp_path / "Vetements.xlsx"
    _make_xlsx(p)
    rows = parse_objectif_xlsx(p)
    assert len(rows) == 2
    assert rows[0] == {
        "nom": "T-shirts", "ordre": 0, "quantite_objectif": 2,
        "echelle": ["Uniqlo U", "Beams Plus", "Visvim"],
    }
    assert rows[1]["echelle"] == ["Uniqlo"]  # dédupliqué


def test_sync_objectif_wipes_and_refills(tmp_path):
    p = tmp_path / "Vetements.xlsx"
    _make_xlsx(p)
    with _mem_session() as s:
        s.add(ObjectifType(nom="Obsolète", ordre=0, quantite_objectif=9, echelle=["X"]))
        s.commit()
        n = sync_objectif(s, p)
        assert n == 2
        from sqlmodel import select
        noms = {t.nom for t in s.exec(select(ObjectifType)).all()}
        assert noms == {"T-shirts", "Polos"}  # ancien effacé
