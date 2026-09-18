from __future__ import annotations

import json

import pytest

from app.api.data import routes
from app.core.config import settings
from app.services.backup_storage import backup_bytes, backup_file


def test_file_backup_is_verified_under_the_configured_nas(tmp_path, monkeypatch):
    nas = tmp_path / "nas"
    monkeypatch.setattr(settings, "backup_dir", str(nas))
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"workbook contents")

    result = backup_file(
        source,
        category="runtime/voyage",
        filename="Voyage.backup-20260913.xlsx",
    )

    assert result == nas / "files" / "runtime" / "voyage" / "Voyage.backup-20260913.xlsx"
    assert result.read_bytes() == source.read_bytes()
    assert source.read_bytes() == b"workbook contents"
    assert not list(result.parent.glob("*.partial"))


def test_backup_refuses_to_fall_back_to_local_when_nas_is_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", "")
    source = tmp_path / "source.csv"
    source.write_text("before", encoding="utf-8")

    with pytest.raises(RuntimeError, match="BACKUP_DIR"):
        backup_file(source, category="runtime/finance-catalog", filename="source.bak.csv")

    assert source.read_text(encoding="utf-8") == "before"
    assert not (tmp_path / "files").exists()


def test_json_export_is_archived_to_nas_before_download(tmp_path, monkeypatch):
    nas = tmp_path / "nas"
    monkeypatch.setattr(settings, "backup_dir", str(nas))
    monkeypatch.setattr(routes.io_svc, "export_all", lambda session: {"tables": {"book": []}})

    response = routes.export_all(session=object())

    archived = list((nas / "files" / "runtime" / "exports-json").glob("*.json"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text(encoding="utf-8")) == {"tables": {"book": []}}
    assert json.loads(response.body) == {"tables": {"book": []}}
