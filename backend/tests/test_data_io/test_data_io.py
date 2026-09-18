"""Tests export/import (#174/#175/#179), CSV (#181), backup (#176/#177), démo (#178)."""

import datetime as dt
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.budget import BudgetTransaction
from app.models.journal import MoodEntry
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
    # robot_conversation retiré : module Robot/IA supprimé (2026-06-09).
    for t in ("budget_transaction", "book", "habit", "music_track"):
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


def test_preview_reports_counts_and_invalid_rows_without_writing():
    s = _session()
    s.add(Book(titre="À conserver", auteur="X", statut="lu"))
    s.commit()

    preview = io.preview_import(s, {
        "version": io.EXPORT_VERSION,
        "exported_at": "2026-09-13T12:00:00+00:00",
        "tables": {
            "book": [{"titre": "Nouveau", "auteur": "Y", "statut": "a_lire"}],
            "budget_transaction": [{"date": "2026-09-13"}],
            "future_table": [{"id": 1}],
        },
    })

    assert preview["can_import"] is False
    assert preview["total_incoming"] == 2
    assert preview["tables"]["book"] == {"incoming": 1, "current": 1}
    assert preview["skipped_tables"] == ["future_table"]
    assert preview["errors"][0]["table"] == "budget_transaction"
    # Preview is read-only, even when it finds an invalid row.
    assert [book.titre for book in s.exec(select(Book)).all()] == ["À conserver"]


def test_invalid_preflight_does_not_delete_existing_rows():
    s = _session()
    s.add(Book(titre="À conserver", auteur="X", statut="lu"))
    s.commit()

    try:
        io.import_all(s, {"tables": {
            "book": [{"titre": "Nouveau", "auteur": "Y", "statut": "a_lire"}],
            "budget_transaction": [{"date": "2026-09-13"}],
        }}, mode="replace")
        assert False, "Une prévalidation invalide doit refuser toute restauration."
    except io.BackupValidationError:
        pass

    assert [book.titre for book in s.exec(select(Book)).all()] == ["À conserver"]


def test_database_error_rolls_back_the_entire_replace():
    s = _session()
    s.add(Book(titre="À conserver", auteur="X", statut="lu"))
    s.add(MoodEntry(date=dt.date(2026, 9, 1), humeur=3, energie=3))
    s.commit()

    dump = {"tables": {
        "book": [{"titre": "Nouveau", "auteur": "Y", "statut": "a_lire"}],
        # Both rows validate as models, then violate the table's unique date constraint.
        "mood_entry": [
            {"date": "2026-09-02", "humeur": 4, "energie": 4},
            {"date": "2026-09-02", "humeur": 5, "energie": 5},
        ],
    }}

    try:
        io.import_all(s, dump, mode="replace")
        assert False, "La contrainte SQL doit faire échouer la restauration."
    except io.BackupRestoreError:
        pass

    books = s.exec(select(Book)).all()
    moods = s.exec(select(MoodEntry)).all()
    assert [book.titre for book in books] == ["À conserver"]
    assert len(moods) == 1 and moods[0].date == dt.date(2026, 9, 1)


def test_import_reports_invalid_rows():
    s = _session()
    # A malformed row now rejects the whole backup before any table is changed.
    dump = {"tables": {"budget_transaction": [{"date": "2026-06-01"}]}}
    try:
        io.import_all(s, dump, mode="replace")
        assert False, "Une ligne invalide doit faire refuser toute la restauration."
    except io.BackupValidationError:
        pass
    assert s.exec(select(BudgetTransaction)).all() == []


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


def test_prune_backups_keeps_everything_when_retention_is_zero(tmp_path):
    for i in range(5):
        (tmp_path / f"2026-06-0{i+1}.db").write_bytes(b"x")

    removed = prune_backups(tmp_path, keep=0)

    assert removed == 0
    assert len(list(tmp_path.glob("*.db"))) == 5


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
