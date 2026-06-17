import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction
from app.services.budget.imports import (
    _parse_desjardins,
    _parse_generic,
    import_csv,
    import_ofx,
    import_transactions,
    parse_ofx,
)


_OFX_SAMPLE = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260515120000.000[-5:EST]
<TRNAMT>-45.32
<NAME>METRO INC
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260516
<TRNAMT>3000.00
<NAME>SALAIRE
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""


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


# ─── OFX (#256) ──────────────────────────────────────────────────────────────

def test_parse_ofx_extracts_transactions():
    txns = parse_ofx(_OFX_SAMPLE)
    assert txns == [
        (dt.date(2026, 5, 15), -45.32, "METRO INC"),
        (dt.date(2026, 5, 16), 3000.0, "SALAIRE"),
    ]


def test_parse_ofx_falls_back_to_memo_when_no_name():
    block = (
        "<OFX><STMTTRN><DTPOSTED>20260601<TRNAMT>-12.50"
        "<MEMO>PAIEMENT SANS NOM</STMTTRN></OFX>"
    )
    assert parse_ofx(block) == [(dt.date(2026, 6, 1), -12.50, "PAIEMENT SANS NOM")]


def test_parse_ofx_empty_when_not_ofx():
    assert parse_ofx("date,marchand,montant\n2026-01-01,X,-1\n") == []


def test_import_ofx_auto_categorises_via_rules(session):
    cat = BudgetCategory(nom="Épicerie")
    session.add(cat); session.commit(); session.refresh(cat)
    session.add(BudgetRule(pattern="METRO|IGA", category_id=cat.id, priorite=1)); session.commit()

    res = import_ofx(session, _OFX_SAMPLE, compte="desjardins")
    assert res["imported"] == 2
    assert res["categorised"] == 1
    assert res["format"] == "ofx"
    txs = session.exec(select(BudgetTransaction)).all()
    assert all(t.compte == "desjardins" for t in txs)
    metro = next(t for t in txs if "METRO" in t.marchand)
    assert metro.category_id == cat.id


def test_import_transactions_dispatches_ofx_vs_csv(session):
    res_ofx = import_transactions(session, _OFX_SAMPLE)
    assert res_ofx["format"] == "ofx" and res_ofx["imported"] == 2

    csv_content = "date,marchand,montant\n2026-05-15,METRO INC,-45.32\n"
    res_csv = import_transactions(session, csv_content)
    assert res_csv["format"] != "ofx" and res_csv["imported"] == 1
