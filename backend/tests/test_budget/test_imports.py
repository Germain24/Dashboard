import datetime as dt
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel, select

from alembic import command
from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction
from app.services.budget.imports import (
    _looks_like_accesd,
    _parse_desjardins,
    _parse_generic,
    import_csv,
    import_ofx,
    import_transactions,
    parse_desjardins_accesd,
    parse_ofx,
)

# Export CSV AccèsD Desjardins (14 colonnes, sans en-tête) : col 7 = retrait
# (dépense), col 8 = dépôt (revenu), col 13 = solde.
_ACCESD = (
    '"Caisse","165906","EOP","2025/10/02",00001,"Achat /ALFID SERVICES","",655.00,"","","","","",1063.32\n'
    '"Caisse","165906","EOP","2025/10/09",00003,"Paie /Le Petit Dep","","",47.43,"","","","",1072.12\n'
    '"Caisse","165906","EOP","2025/10/05",00005,"Virement - AccesD Internet /a ET 1","",100.00,"","","","","",900.00\n'
    '"Caisse","165906","EOP","2025/10/06",00006,"Paiement facture - AccesD Internet /Remises Mastercard Desjardins","",135.86,"","","","","",764.14\n'
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
    session.add(cat)
    session.commit()
    session.refresh(cat)
    session.add(BudgetRule(pattern="METRO|IGA", category_id=cat.id, priorite=1))
    session.commit()

    csv_content = "date,marchand,montant\n2026-05-15,METRO INC,-45.32\n2026-05-16,INCONNU XYZ,-10.00\n"
    res = import_csv(session, csv_content)

    assert res["imported"] == 2
    assert res["categorised"] == 1  # METRO catégorisé, INCONNU non
    txs = session.exec(select(BudgetTransaction)).all()
    metro = next(t for t in txs if "METRO" in t.marchand)
    assert metro.category_id == cat.id


def test_reimport_csv_is_idempotent_and_keeps_identical_purchases(session):
    # Two truly separate purchases with identical visible fields must both be
    # retained on first import, then both recognized on the same re-import.
    csv_content = (
        "date,marchand,montant\n"
        "2026-05-15,METRO INC,-45.32\n"
        "2026-05-15,METRO INC,-45.32\n"
    )

    first = import_csv(session, csv_content, compte="desjardins")
    second = import_csv(session, csv_content, compte="desjardins")

    txs = session.exec(select(BudgetTransaction)).all()
    assert first["imported"] == 2 and first["skipped"] == 0
    assert second["imported"] == 0 and second["skipped"] == 2
    assert len(txs) == 2
    assert {tx.import_source for tx in txs} == {"csv:generic"}
    assert len({tx.import_fingerprint for tx in txs}) == 2
    assert all(len(tx.import_fingerprint) == 64 for tx in txs)


def test_import_fingerprint_migration_preserves_legacy_transaction(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[2]
    db_url = f"sqlite:///{tmp_path / 'legacy-budget.db'}"
    monkeypatch.setenv("ALEMBIC_DB_URL", db_url)
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))

    # Build the existing schema, insert a pre-migration row, and upgrade only
    # through the new additive revision. No application/runtime database is used.
    command.upgrade(config, "fcatmeta20260827")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        result = connection.execute(text(
            "INSERT INTO budget_transaction "
            "(date, montant, marchand, description, category_id, compte, devise, auto, tags, created_at) "
            "VALUES ('2026-09-01', -12.5, 'Ancien achat', '', NULL, 'principal', 'CAD', 0, '[]', "
            "'2026-09-13 12:00:00')"
        ))
        legacy_id = result.lastrowid

    command.upgrade(config, "budgetimport20260913")
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT id, date, montant, marchand, import_source, import_external_id, "
            "import_fingerprint FROM budget_transaction WHERE id = :id"
        ), {"id": legacy_id}).one()
    indexes = inspect(engine).get_indexes("budget_transaction")
    engine.dispose()

    assert row.date == "2026-09-01" and row.marchand == "Ancien achat"
    assert row.import_source is None and row.import_external_id is None
    assert row.import_fingerprint is None
    assert any(
        index["name"] == "ix_budget_transaction_import_fingerprint" and index["unique"]
        for index in indexes
    )


def test_legacy_transactions_without_fingerprint_still_prevent_reimport(session):
    # The migration leaves historical rows null; semantic matching bridges them
    # without changing or deleting the pre-existing record.
    legacy = BudgetTransaction(
        date=dt.date(2026, 5, 15), montant=-45.32, marchand="METRO INC",
        compte="desjardins", devise="CAD",
    )
    session.add(legacy)
    session.commit()

    result = import_csv(
        session,
        "date,marchand,montant\n2026-05-15,METRO INC,-45.32\n",
        compte="desjardins",
    )

    txs = session.exec(select(BudgetTransaction)).all()
    assert result["imported"] == 0 and result["skipped"] == 1
    assert len(txs) == 1
    assert txs[0].import_fingerprint is None and txs[0].import_source is None


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
    session.add(cat)
    session.commit()
    session.refresh(cat)
    session.add(BudgetRule(pattern="METRO|IGA", category_id=cat.id, priorite=1))
    session.commit()

    res = import_ofx(session, _OFX_SAMPLE, compte="desjardins")
    assert res["imported"] == 2
    assert res["categorised"] == 1
    assert res["format"] == "ofx"
    txs = session.exec(select(BudgetTransaction)).all()
    assert all(t.compte == "desjardins" for t in txs)
    metro = next(t for t in txs if "METRO" in t.marchand)
    assert metro.category_id == cat.id


def test_reimport_ofx_uses_stable_fitid_even_if_statement_text_changes(session):
    original = """OFXHEADER:100
<OFX><STMTTRN><DTPOSTED>20260515<TRNAMT>-45.32
<FITID>BANK-TRN-0042<NAME>METRO INC</STMTTRN></OFX>"""
    revised = """OFXHEADER:100
<OFX><STMTTRN><DTPOSTED>20260516<TRNAMT>-46.00
<FITID>BANK-TRN-0042<NAME>METRO INCORPORATED</STMTTRN></OFX>"""

    first = import_ofx(session, original, compte="desjardins")
    second = import_ofx(session, revised, compte="desjardins")

    txs = session.exec(select(BudgetTransaction)).all()
    assert first["imported"] == 1
    assert second["imported"] == 0 and second["skipped"] == 1
    assert len(txs) == 1
    assert txs[0].import_source == "ofx"
    assert txs[0].import_external_id == "BANK-TRN-0042"
    assert txs[0].marchand == "METRO INC"  # corrected export didn't overwrite user data


def test_parse_accesd_signs_and_exclusions():
    out = parse_desjardins_accesd(_ACCESD)
    assert (dt.date(2025, 10, 2), -655.00, "Achat /ALFID SERVICES") in out      # retrait → dépense
    assert (dt.date(2025, 10, 9), 47.43, "Paie /Le Petit Dep") in out           # dépôt → revenu
    libelles = [d[2] for d in out]
    assert not any("ET 1" in m for m in libelles)            # transfert interne exclu
    assert not any("Remises Mastercard" in m for m in libelles)  # paiement carte exclu
    assert len(out) == 2


def test_looks_like_accesd_detects_format():
    assert _looks_like_accesd(_ACCESD) is True
    assert _looks_like_accesd("date,marchand,montant\n2026-01-01,X,-1\n") is False


def test_import_transactions_dispatches_accesd(session):
    res = import_transactions(session, _ACCESD)
    assert res["format"] == "desjardins-debit"
    assert res["imported"] == 2

    repeated = import_transactions(session, _ACCESD)
    assert repeated["imported"] == 0 and repeated["skipped"] == 2
    txs = session.exec(select(BudgetTransaction)).all()
    assert len(txs) == 2
    assert all(tx.import_source == "desjardins-accesd" for tx in txs)
    assert all(tx.import_external_id for tx in txs)


def test_import_transactions_dispatches_ofx_and_deduplicates_csv_copy(session):
    res_ofx = import_transactions(session, _OFX_SAMPLE)
    assert res_ofx["format"] == "ofx" and res_ofx["imported"] == 2

    # This row is already in the OFX statement, so importing the same operation
    # from a CSV export must not create a second budget entry.
    csv_content = "date,marchand,montant\n2026-05-15,METRO INC,-45.32\n"
    res_csv = import_transactions(session, csv_content)
    assert res_csv["format"] != "ofx" and res_csv["imported"] == 0
    assert res_csv["skipped"] == 1
    assert len(session.exec(select(BudgetTransaction)).all()) == 2
