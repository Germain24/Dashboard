import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction
from app.services.budget.imports import _parse_desjardins, _parse_generic, import_csv


def test_parse_generic():
    row = ["2026-05-15", "METRO INC", "-45.32"]
    assert _parse_generic(row) == (dt.date(2026, 5, 15), -45.32, "METRO INC")


def test_parse_desjardins_debit():
    row = ["2026-05-15", "STARBUCKS", "6.75", "", "1200.00"]
    result = _parse_desjardins(row)
    assert result is not None
    assert result[1] == -6.75


def test_parse_desjardins_credit():
    row = ["2026-05-01", "SALAIRE", "", "3000.00", "4200.00"]
    result = _parse_desjardins(row)
    assert result is not None
    assert result[1] == 3000.0


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/b.db", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_import_auto_categorises_via_rules(session):
    cat = BudgetCategory(nom="Épicerie")
    session.add(cat); session.commit(); session.refresh(cat)
    session.add(BudgetRule(pattern="METRO|IGA", category_id=cat.id, priorite=1)); session.commit()

    csv_content = "date,marchand,montant\n2026-05-15,METRO INC,-45.32\n2026-05-16,INCONNU XYZ,-10.00\n"
    res = import_csv(session, csv_content)

    assert res["imported"] == 2
    assert res["categorised"] == 1  # METRO catégorisé, INCONNU non
    txs = session.exec(select(BudgetTransaction)).all()
    metro = next(t for t in txs if "METRO" in t.marchand)
    assert metro.category_id == cat.id
