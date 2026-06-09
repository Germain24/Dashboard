"""Tests purge (#172) et préférences de notification (#171)."""

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.scheduler import JobRun, Notification
from app.services.scheduler import notif_prefs
from app.services.scheduler.purge import cutoff, purge_old


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


# ── Purge (#172) ─────────────────────────────────────────────────────────────

def test_cutoff_pure():
    now = dt.datetime(2026, 6, 9, 12, 0, 0)
    assert cutoff(now, 30) == dt.datetime(2026, 5, 10, 12, 0, 0)


def test_purge_removes_old_jobruns_and_read_notifs():
    s = _session()
    now = dt.datetime(2026, 6, 9, 12, 0, 0)
    old = now - dt.timedelta(days=40)
    recent = now - dt.timedelta(days=2)

    s.add(JobRun(job_id="x", started_at=old, status="success"))
    s.add(JobRun(job_id="x", started_at=recent, status="success"))
    s.add(Notification(titre="vieux lu", lu=True, created_at=old))
    s.add(Notification(titre="vieux non lu", lu=False, created_at=old))   # conservé
    s.add(Notification(titre="recent lu", lu=True, created_at=recent))    # conservé
    s.commit()

    res = purge_old(s, now=now, jobrun_days=30, notif_days=30)
    assert res["job_runs"] == 1
    assert res["notifications"] == 1

    assert len(s.exec(select(JobRun)).all()) == 1
    notifs = s.exec(select(Notification)).all()
    titres = {n.titre for n in notifs}
    assert titres == {"vieux non lu", "recent lu"}


# ── Préférences (#171) ───────────────────────────────────────────────────────

def test_prefs_default_enabled(tmp_path):
    assert notif_prefs.is_enabled("finance_snapshot", path=tmp_path / "p.json") is True


def test_prefs_disable_then_filter(tmp_path):
    p = tmp_path / "p.json"
    notif_prefs.set_source("finance_snapshot", False, path=p)
    assert notif_prefs.is_enabled("finance_snapshot", path=p) is False
    assert notif_prefs.is_enabled("habit_reminder", path=p) is True


def test_filter_enabled(tmp_path):
    p = tmp_path / "p.json"
    notif_prefs.set_source("spam", False, path=p)

    class N:
        def __init__(self, source):
            self.source = source

    rows = [N("spam"), N("finance_snapshot"), N("spam")]
    kept = notif_prefs.filter_enabled(rows, path=p)
    assert len(kept) == 1
    assert kept[0].source == "finance_snapshot"
