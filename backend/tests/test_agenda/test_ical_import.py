"""Import iCal mutualisé + dédup (#83/#91)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.agenda.ical_import import import_ics_bytes

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//FR
BEGIN:VEVENT
UID:evt-1@test
SUMMARY:Cours maths
DTSTART:20260603T090000
DTEND:20260603T100000
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_import_creates_event(session):
    counts = import_ics_bytes(session, ICS)
    assert counts["created_events"] == 1
    assert counts["skipped_duplicates"] == 0


def test_reimport_dedups_by_uid(session):
    import_ics_bytes(session, ICS)
    counts = import_ics_bytes(session, ICS)
    assert counts["created_events"] == 0
    assert counts["skipped_duplicates"] == 1
