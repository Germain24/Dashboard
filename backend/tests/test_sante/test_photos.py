"""Photos de progression avant/après (#69)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.sante import photos


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_save_writes_file_and_sets_url(session, tmp_path):
    d = dt.date(2026, 6, 3)
    m = photos.save_progress_photo(session, d, "selfie.PNG", b"\x89PNG-bytes", base_dir=tmp_path)
    assert m.photo_url == "/media/sante/2026-06-03.png"
    assert (tmp_path / "2026-06-03.png").read_bytes() == b"\x89PNG-bytes"


def test_unknown_extension_falls_back_to_jpg(session, tmp_path):
    m = photos.save_progress_photo(session, dt.date(2026, 6, 4), "x.gif", b"data", base_dir=tmp_path)
    assert m.photo_url.endswith("2026-06-04.jpg")


def test_empty_content_rejected(session, tmp_path):
    with pytest.raises(ValueError):
        photos.save_progress_photo(session, dt.date(2026, 6, 5), "a.jpg", b"", base_dir=tmp_path)


def test_list_returns_only_photo_rows(session, tmp_path):
    photos.save_progress_photo(session, dt.date(2026, 6, 1), "a.jpg", b"1", base_dir=tmp_path)
    photos.save_progress_photo(session, dt.date(2026, 6, 3), "b.jpg", b"2", base_dir=tmp_path)
    out = photos.list_progress_photos(session)
    assert [p["date"] for p in out] == ["2026-06-01", "2026-06-03"]
