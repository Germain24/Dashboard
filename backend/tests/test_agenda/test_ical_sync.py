"""Synchro iCal externe : service URL + job périodique (Agendrix)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.agenda import ical_import
from app.services.agenda import ical_source
from app.services.scheduler.jobs import ical_sync

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//FR
BEGIN:VEVENT
UID:shift-1@agendrix
SUMMARY:Shift 9-17
DTSTART:20260603T090000
DTEND:20260603T170000
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def isolate_calendar_source(monkeypatch, tmp_path):
    monkeypatch.setattr(ical_source, "_path", lambda: tmp_path / "ical_source.json")


class _Resp:
    headers = {"content-length": str(len(ICS))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield ICS


def test_import_from_url_rejects_non_http(session):
    with pytest.raises(ValueError):
        ical_import.import_ics_from_url(session, "ftp://nope.ics")


def test_import_from_url_fetches_and_imports(session, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Resp())
    counts = ical_import.import_ics_from_url(session, "https://app.agendrix.com/cal.ics")
    assert counts["created_events"] == 1


def test_import_updates_a_shift_when_the_feed_changes(session):
    changed = ICS.replace(b"Shift 9-17", b"Shift 10-18").replace(
        b"20260603T090000", b"20260603T100000"
    ).replace(b"20260603T170000", b"20260603T180000")

    first = ical_import.import_ics_bytes(session, ICS, source_key="work", category="travail")
    second = ical_import.import_ics_bytes(session, changed, source_key="work", category="travail")

    from sqlmodel import select
    from app.models.agenda import Evenement
    event = session.exec(select(Evenement)).one()
    assert first["created_events"] == 1
    assert second["updated_events"] == 1
    assert event.titre == "Shift 10-18"
    assert event.debut.hour == 10
    assert event.source_id == "work:shift-1@agendrix"
    assert event.categorie == "travail"


def test_calendar_source_status_never_exposes_the_secret_url(monkeypatch, tmp_path):
    monkeypatch.setattr(ical_source, "_path", lambda: tmp_path / "source.json")
    secret = "https://app.7shifts.com/calendar/private-token"
    result = ical_source.configure(secret, "7shifts")

    assert result["configured"] is True
    assert secret not in str(result)
    assert "url" not in result


def test_calendar_source_accepts_only_the_7shifts_host(monkeypatch, tmp_path):
    monkeypatch.setattr(ical_source, "_path", lambda: tmp_path / "source.json")
    with pytest.raises(ValueError):
        ical_source.configure("https://example.com/feed.ics")


def test_job_no_url_configured_is_inactive(session, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "ical_sync_urls", "")
    assert "aucune URL" in ical_sync.run(session)


def test_job_imports_configured_urls(session, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "ical_sync_urls", "https://a.ics, https://b.ics")

    calls: list[str] = []

    def fake_import(sess, url, **kw):
        calls.append(url)
        return {"created_events": 2, "skipped_duplicates": 1, "created_rules": 0}

    monkeypatch.setattr(ical_import, "import_ics_from_url", fake_import)
    msg = ical_sync.run(session)
    assert calls == ["https://a.ics", "https://b.ics"]
    assert "4 ajouté(s)" in msg   # 2 + 2
    assert "2 déjà présent(s)" in msg  # 1 + 1


def test_job_counts_failures(session, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "ical_sync_urls", "https://bad.ics")

    def boom(sess, url, **kw):
        raise RuntimeError("injoignable")

    monkeypatch.setattr(ical_import, "import_ics_from_url", boom)
    msg = ical_sync.run(session)
    assert "1 échec(s)" in msg
