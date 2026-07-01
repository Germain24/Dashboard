"""Import Voyage.xlsx -> cache lieu_voyage."""
from __future__ import annotations

import openpyxl
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.voyage import LieuVoyage
from app.services.voyage.import_excel import parse_voyage_xlsx, sync_voyage


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre",
               "Aéroport (IATA)", "Jours min", "Jours max", "Coût/jour estimé"])
    ws.append(["Table Mountain", "Le Cap", "Afrique du Sud", False, 1, "CPT", 2, 4, 80])
    ws.append(["K-2", "K-2", "Chine", False, 5, None, None, None, None])  # incomplet
    ws.append(["Robben Island", "Le Cap", "Afrique du Sud", True, None, "CPT", 1, 1, 60])  # déjà visité
    ws.append([None, None, None, None, None, None, None, None, None])  # ligne vide -> ignorée
    wb.save(path)


def test_parse_voyage_xlsx(tmp_path):
    p = tmp_path / "Voyage.xlsx"
    _make_xlsx(p)
    rows = parse_voyage_xlsx(p)
    assert len(rows) == 3
    assert rows[0] == {
        "nom": "Table Mountain", "ville": "Le Cap", "pays": "Afrique du Sud", "visite": False,
        "aeroport_iata": "CPT", "jours_min": 2, "jours_max": 4, "cout_jour_estime": 80.0,
    }
    assert rows[1]["aeroport_iata"] is None
    assert rows[1]["jours_min"] is None
    assert rows[2]["visite"] is True


def test_sync_voyage_wipes_and_refills_and_flags_incomplete(tmp_path, session):
    p = tmp_path / "Voyage.xlsx"
    _make_xlsx(p)
    session.add(LieuVoyage(nom="Obsolète"))
    session.commit()

    result = sync_voyage(session, p)

    assert result["lieux"] == 3
    assert result["incomplets"] == ["K-2"]  # non visité + aéroport/jours manquants
    noms = {lv.nom for lv in session.exec(select(LieuVoyage)).all()}
    assert noms == {"Table Mountain", "K-2", "Robben Island"}  # ancien "Obsolète" effacé


def test_sync_voyage_does_not_flag_incomplete_if_already_visited(tmp_path, session):
    p = tmp_path / "Voyage.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lieux", "Ville (ou ville la plus proche)", "Pays", "Visité", "Ordre",
               "Aéroport (IATA)", "Jours min", "Jours max", "Coût/jour estimé"])
    ws.append(["Déjà fait", "Paris", "France", True, None, None, None, None, None])
    wb.save(p)

    result = sync_voyage(session, p)
    assert result["incomplets"] == []
