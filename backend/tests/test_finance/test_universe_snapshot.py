from __future__ import annotations

from pathlib import Path

import pytest

from app.services.finance.buffett.universe_snapshot import create_universe_snapshot, snapshot_path


def test_resume_uses_immutable_snapshot_after_catalog_change(tmp_path: Path):
    source = tmp_path / "tickers.csv"
    source.write_text("AAPL;Apple;Nasdaq;EQUITY\n", encoding="utf-8")
    meta = create_universe_snapshot(source, run_id=53, destination_dir=tmp_path / "snapshots")
    source.write_text("MSFT;Microsoft;Nasdaq;EQUITY\n", encoding="utf-8")

    selected = Path(snapshot_path({"universe_snapshot": meta}, str(source)))
    assert selected.read_text(encoding="utf-8").startswith("AAPL;")
    assert meta["source_checksum"]
    assert meta["snapshot_checksum"]
    assert meta["n_tickers"] == 1


def test_snapshot_checksum_detects_tampering(tmp_path: Path):
    source = tmp_path / "tickers.csv"
    source.write_text("AAPL;Apple;Nasdaq;EQUITY\n", encoding="utf-8")
    meta = create_universe_snapshot(source, run_id=54, destination_dir=tmp_path / "snapshots")
    Path(meta["snapshot_path"]).write_text("MSFT\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="checksum"):
        snapshot_path({"universe_snapshot": meta}, str(source))


def test_reused_sqlite_run_id_gets_fingerprinted_snapshot(tmp_path: Path):
    source = tmp_path / "tickers.csv"
    snapshots = tmp_path / "snapshots"
    source.write_text("AAPL;Apple;Nasdaq;EQUITY\n", encoding="utf-8")
    first = create_universe_snapshot(source, run_id=54, destination_dir=snapshots)

    source.write_text("MSFT;Microsoft;Nasdaq;EQUITY\n", encoding="utf-8")
    second = create_universe_snapshot(source, run_id=54, destination_dir=snapshots)

    assert first["snapshot_path"] != second["snapshot_path"]
    assert Path(first["snapshot_path"]).read_text(encoding="utf-8").startswith("AAPL;")
    assert Path(second["snapshot_path"]).read_text(encoding="utf-8").startswith("MSFT;")
    assert "_54_" in Path(second["snapshot_path"]).name
