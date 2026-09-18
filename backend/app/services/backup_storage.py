"""Verified file backups stored on the configured NAS, with no local fallback."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath

from app.core.config import settings


def backup_file(source: str | Path, *, category: str, filename: str) -> Path:
    """Copy ``source`` under BACKUP_DIR/files and verify it before returning.

    The temporary file and final file are on the same NAS directory so the
    final rename is atomic. Callers should make this copy before mutating the
    source; a missing or unavailable NAS therefore stops the mutation.
    """
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"Fichier à sauvegarder introuvable : {source_path}")

    destination = _destination(category, filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Le backup existe déjà et sera conservé : {destination}")

    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    try:
        shutil.copy2(source_path, temporary)
        if source_path.stat().st_size != temporary.stat().st_size:
            raise OSError(f"Taille incorrecte pour la copie de sauvegarde : {temporary}")
        if _sha256(source_path) != _sha256(temporary):
            raise OSError(f"Empreinte SHA-256 incorrecte pour la copie : {temporary}")
        os.replace(temporary, destination)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return destination


def backup_bytes(content: str | bytes, *, category: str, filename: str) -> Path:
    """Persist an in-memory backup payload on the NAS and verify it atomically."""
    payload = content.encode("utf-8") if isinstance(content, str) else content
    destination = _destination(category, filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Le backup existe déjà et sera conservé : {destination}")

    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
        if temporary.stat().st_size != len(payload) or _sha256(temporary) != hashlib.sha256(payload).hexdigest():
            raise OSError(f"Vérification incorrecte pour la copie de sauvegarde : {temporary}")
        os.replace(temporary, destination)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return destination


def _destination(category: str, filename: str) -> Path:
    configured_dir = getattr(settings, "backup_dir", None)
    if not configured_dir or not str(configured_dir).strip():
        raise RuntimeError("BACKUP_DIR n'est pas configuré : sauvegarde NAS impossible.")

    category_path = PurePosixPath(category.replace("\\", "/"))
    if (
        category_path.is_absolute()
        or not category_path.parts
        or any(part in {"", ".", ".."} for part in category_path.parts)
        or any(not re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in category_path.parts)
    ):
        raise ValueError(f"Catégorie de sauvegarde invalide : {category!r}")

    name = Path(filename).name
    if name != filename or name in {"", ".", ".."}:
        raise ValueError("Le nom du backup doit être un nom de fichier simple.")

    return Path(configured_dir) / "files" / Path(*category_path.parts) / name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
