"""Tests export/import (#174/#175/#179), CSV (#181), backup (#176/#177), démo (#178)."""

import datetime as dt
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.budget import BudgetTransaction
from app.models.livres import Book
from app.services.data_io import demo as demo_svc
from app.services.data_io import export_import as io
from app.services.scheduler.jobs.backup_db import integrity_ok, prune_backups


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


# ── Export / import (#174/#175) ──────────────────────────────────────────────

def test_table_models_discovers_known_tables():
    models = io.table_models()
    for t in ("budget_transaction", "book", "habit", "robot_conversation"):
        assert t in models


def test_export_then_import_roundtrip():
    s1 = _session()
    s1.add(BudgetTransaction(date=dt.date(2026, 6, 1), montant=-20.0, marchand="Test"))
    s1.add(Book(titre="Sapiens", auteur="Harari", statut="lu"))
    s1.commit()

    dump = io.export_all(s1)
    assert dump["version"] == io.EXPORT_VERSION
    assert len(dump["tables"]["budget_transaction"]) == 1
    assert len(dump["tables"]["book"]) == 1

    s2 = _session()
    report = io.import_all(s2, dump, mode="replace")
    assert report["total_inserted"] >= 2
    assert report["tables"]["book"]["inserted"] == 1
    assert len(s2.exec(select(Book)).all()) == 1
    assert s2.exec(select(BudgetTransaction)).first().montant == -20.0


def test_import_replace_wipes_existing():
    s = _session()
    s.add(Book(titre="Ancien", auteur="X", statut="lu"))
    s.commit()
    dump = {"tables": {"book": [{"titre": "Nouveau", "auteur": "Y", "statut": "a_lire"}]}}
    io.import_all(s, dump, mode="replace")
    books = s.exec(select(Book)).all()
    assert len(books) == 1 and books[0].titre == "Nouveau"


def test_import_reports_invalid_rows():
    s = _session()
    # 'montant' manquant et non nullable -> erreur sur la ligne, pas de crash
    dump = {"tables": {"budget_transaction": [{"date": "2026-06-01"}]}}
    report = io.import_all(s, dump, mode="replace")
    assert report["tables"]["budget_transaction"]["inserted"] == 0
    assert len(report["tables"]["budget_transaction"]["errors"]) == 1


def test_import_skips_unknown_table():
    s = _session()
    report = io.import_all(s, {"tables": {"table_bidon": [{}]}}, mode="replace")
    assert "table_bidon" in report["skipped_tables"]


# ── CSV (#181) ───────────────────────────────────────────────────────────────

def test_export_table_csv():
    s = _session()
    s.add(Book(titre="Dune", auteur="Herbert", statut="a_lire"))
    s.commit()
    csv_str = io.export_table_csv(s, "book")
    assert "titre" in csv_str.splitlines()[0]
    assert "Dune" in csv_str


def test_export_table_csv_unknown():
    assert io.export_table_csv(_session(), "nope") is None


# ── Backup (#176/#177) ───────────────────────────────────────────────────────

def test_prune_backups_keeps_n(tmp_path):
    for i in range(5):
        f = tmp_path / f"2026-06-0{i+1}.db"
        f.write_bytes(b"x")
    removed = prune_backups(tmp_path, keep=3)
    assert removed == 2
    assert len(list(tmp_path.glob("*.db"))) == 3


def test_integrity_ok_on_real_sqlite(tmp_path):
    import sqlite3
    db = tmp_path / "ok.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()
    assert integrity_ok(db) is True


def test_integrity_ko_on_garbage(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not a sqlite file at all")
    assert integrity_ok(bad) is False


# ── Démo (#178) ──────────────────────────────────────────────────────────────

def test_seed_demo_inserts_and_detects():
    s = _session()
    assert demo_svc.has_any_data(s) is False
    counts = demo_svc.seed_demo(s)
    assert counts["budget"] >= 1 and counts["livres"] >= 1
    assert demo_svc.has_any_data(s) is True
    assert len(s.exec(select(Book)).all()) == counts["livres"]
