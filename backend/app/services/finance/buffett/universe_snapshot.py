"""Snapshots immuables de l'univers Buffett.

Une reprise ne doit jamais relire le catalogue courant: le chemin du snapshot et
son checksum sont persistés dans ``BuffettRun.params_json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .ticker_universe import read_ticker_catalog


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_universe_snapshot(
    source: Path,
    *,
    run_id: int,
    destination_dir: Path,
    catalog_version: int | str | None = None,
) -> dict:
    destination_dir.mkdir(parents=True, exist_ok=True)
    catalog = read_ticker_catalog(source, require_canonical=True)
    source_checksum = catalog.diagnostics.source_checksum
    payload = catalog.canonical_bytes()
    checksum = hashlib.sha256(payload).hexdigest()
    target = destination_dir / f"run_{run_id}_tickers.csv"
    # SQLite peut réutiliser un identifiant après suppression du dernier run.
    # L'ancien snapshot reste volontairement immuable : le nouveau reçoit alors
    # un nom fingerprinté au lieu d'écraser ou de bloquer le nouveau run.
    if target.exists() and file_checksum(target) != checksum:
        target = destination_dir / f"run_{run_id}_{checksum[:12]}_tickers.csv"
    metadata = target.with_name(target.name.replace("_tickers.csv", "_universe.json"))
    if target.exists():
        if file_checksum(target) != checksum:
            raise RuntimeError(f"snapshot immuable déjà présent avec un autre contenu: {target}")
    else:
        fd, temp_name = tempfile.mkstemp(prefix=".universe-", dir=destination_dir)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    meta = {
        "run_id": run_id,
        "source_path": str(source.resolve()),
        "snapshot_path": str(target.resolve()),
        "catalog_version": catalog_version,
        "source_checksum": source_checksum,
        "snapshot_checksum": checksum,
        # Ancien nom conservé pour les snapshots/clients existants.
        "catalog_checksum": checksum,
        "n_tickers": len(catalog.tickers),
        "diagnostics": catalog.diagnostics.as_dict(),
    }
    metadata.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def snapshot_path(params: dict | None, fallback: str) -> str:
    """Retourne le snapshot persisté, ou le fallback pour les anciens runs."""
    value = (params or {}).get("universe_snapshot")
    if isinstance(value, dict):
        path = value.get("snapshot_path")
        if path and Path(path).exists():
            expected = value.get("snapshot_checksum") or value.get("catalog_checksum")
            if expected and file_checksum(Path(path)) != expected:
                raise RuntimeError("checksum du snapshot d'univers invalide")
            return str(path)
    return fallback
