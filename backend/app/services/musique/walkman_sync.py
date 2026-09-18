"""Copie idempotente et conversion de la bibliothèque vers le Walkman."""
from __future__ import annotations

import math
import os
import re
import shutil
import tempfile
import threading
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.realtime import publish

AAC_BITRATE = 320_000
FREE_SPACE_RESERVE = 100 * 1024 * 1024
SUPPORTED_SUFFIXES = {".mp3", ".flac", ".dsf"}
TAG_KEYS = ("title", "artist", "album", "albumartist", "genre", "date", "tracknumber", "discnumber")

_LOCK = threading.Lock()
_PROGRESS: dict[str, Any] = {
    "active": False,
    "status": "idle",
    "phase": None,
    "n_done": 0,
    "n_total": 0,
    "current_file": None,
    "copied": 0,
    "converted": 0,
    "identical": 0,
    "replaced": 0,
    "skipped_capacity": 0,
    "skipped_priority": 0,
    "failed": 0,
    "error": None,
}


def get_progress() -> dict[str, Any]:
    with _LOCK:
        return dict(_PROGRESS)


def begin_sync() -> bool:
    """Réserve l'unique tâche avant son envoi au thread de fond."""
    with _LOCK:
        if _PROGRESS["active"]:
            return False
        _PROGRESS.update(
            active=True,
            status="running",
            phase="preparing",
            n_done=0,
            n_total=0,
            current_file=None,
            copied=0,
            converted=0,
            identical=0,
            replaced=0,
            skipped_capacity=0,
            skipped_priority=0,
            failed=0,
            error=None,
        )
    _publish_progress()
    return True


def _update(**values: Any) -> None:
    with _LOCK:
        _PROGRESS.update(values)
    _publish_progress()


def _increment(counter: str) -> None:
    with _LOCK:
        _PROGRESS[counter] += 1
    _publish_progress()


def _publish_progress() -> None:
    progress = get_progress()
    try:
        publish(
            "music.walkman.sync.progress",
            data=progress,
            invalidate=[["musique"]] if not progress["active"] else None,
        )
    except Exception:
        # Le transfert doit pouvoir continuer si un client temps réel est absent.
        pass


def validate_encoder() -> None:
    """Fail fast si la roue PyAV ne fournit pas l'encodeur AAC natif."""
    import av

    av.codec.Codec("aac", "w")


def validate_roots(library_dir: Path, tele_dir: Path, walkman_dir: Path) -> tuple[Path, Path, Path]:
    roots: list[Path] = []
    for label, candidate in (("Musique", library_dir), ("Musique Tele", tele_dir)):
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError(f"Le dossier source {label} est introuvable ou inaccessible.")
        roots.append(candidate.resolve(strict=True))

    if walkman_dir.is_symlink() or not walkman_dir.is_dir():
        raise ValueError("Le Walkman est absent : le dossier de destination est inaccessible.")
    target = walkman_dir.resolve(strict=True)
    for source in roots:
        if target == source or target.is_relative_to(source) or source.is_relative_to(target):
            raise ValueError("La destination du Walkman ne peut pas être dans un dossier source.")
    if not os.access(target, os.W_OK):
        raise ValueError("Le dossier du Walkman n'est pas accessible en écriture.")
    return roots[0], roots[1], target


def _sort_key(path: Path) -> tuple[str, str]:
    raw = path.as_posix()
    normalized = unicodedata.normalize("NFKD", raw.casefold())
    plain = "".join(char for char in normalized if not unicodedata.combining(char))
    return plain, raw.casefold()


def _path_key(path: Path) -> str:
    raw = path.as_posix().replace("\\", "/")
    return unicodedata.normalize("NFC", raw).casefold()


def _list_audio(root: Path) -> list[tuple[Path, Path]]:
    rows: list[tuple[Path, Path]] = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            if not path.resolve(strict=True).is_relative_to(root):
                continue
        except OSError:
            continue
        relative = path.relative_to(root)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        rows.append((path, relative))
    rows.sort(key=lambda row: _sort_key(row[1]))
    return rows


def _destination_relative(source_relative: Path) -> Path:
    suffix = source_relative.suffix.lower()
    if suffix in {".flac", ".dsf"}:
        return source_relative.with_suffix(".m4a")
    return source_relative


def _existing_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if not path.resolve(strict=True).is_relative_to(root):
                continue
        except OSError:
            continue
        result.setdefault(_path_key(path.relative_to(root)), path)
    return result


def _safe_destination(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Chemin de sortie invalide.")
    destination = root.joinpath(*relative.parts)
    if destination.is_symlink():
        raise ValueError("Un lien symbolique empêche l'écriture sûre du morceau.")
    resolved_parent = destination.parent.resolve(strict=False)
    if not resolved_parent.is_relative_to(root):
        raise ValueError("Le chemin de sortie sort du Walkman.")
    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Un lien symbolique empêche l'écriture sûre du morceau.")
    return destination


def _hash(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _easy_tags(path: Path) -> dict[str, str]:
    import mutagen

    audio = mutagen.File(path, easy=True)
    if audio is None or not getattr(audio, "info", None):
        return {}
    tags = getattr(audio, "tags", None) or {}
    result: dict[str, str] = {}
    for key in TAG_KEYS:
        values = tags.get(key)
        if values:
            result[key] = str(values[0] if isinstance(values, (list, tuple)) else values)
    return result


def _duration_seconds(path: Path) -> float:
    import mutagen

    audio = mutagen.File(path, easy=True)
    duration = getattr(getattr(audio, "info", None), "length", None)
    if duration and math.isfinite(float(duration)) and float(duration) > 0:
        return float(duration)

    import av

    with av.open(str(path)) as container:
        stream = next((item for item in container.streams if item.type == "audio"), None)
        if stream is None:
            raise ValueError("Aucune piste audio détectée.")
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
            if duration > 0 and math.isfinite(duration):
                return duration
    raise ValueError("Durée audio inconnue; impossible d'estimer l'espace requis.")


def estimate_output_size(path: Path) -> int:
    if path.suffix.lower() == ".mp3":
        return path.stat().st_size
    # Marge de 2 % pour les conteneurs et 64 Kio pour les balises AAC/MP4.
    return math.ceil(_duration_seconds(path) * AAC_BITRATE / 8 * 1.02) + 64 * 1024


def _write_mp4_tags(path: Path, tags: dict[str, str]) -> None:
    if not tags:
        return
    from mutagen.mp4 import MP4

    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    simple = {
        "title": "\xa9nam",
        "artist": "\xa9ART",
        "album": "\xa9alb",
        "albumartist": "aART",
        "genre": "\xa9gen",
        "date": "\xa9day",
    }
    for source_key, mp4_key in simple.items():
        if tags.get(source_key):
            audio.tags[mp4_key] = [tags[source_key]]
    for source_key, mp4_key in (("tracknumber", "trkn"), ("discnumber", "disk")):
        value = tags.get(source_key)
        if value:
            match = re.match(r"\s*(\d+)(?:\s*/\s*(\d+))?", value)
            if match:
                audio.tags[mp4_key] = [(int(match.group(1)), int(match.group(2) or 0))]
    audio.save()


def encode_to_aac(source: Path, destination: Path) -> None:
    """Transcode vers AAC-LC 320 kbit/s / M4A à l'aide de PyAV et FFmpeg."""
    import av

    tags = _easy_tags(source)
    with av.open(str(source)) as input_container:
        input_stream = next((item for item in input_container.streams if item.type == "audio"), None)
        if input_stream is None:
            raise ValueError("Aucune piste audio détectée.")
        input_layout = input_stream.codec_context.layout
        input_channels = len(input_layout.channels) if input_layout is not None else 2
        output_layout = "mono" if input_channels == 1 else "stereo"
        input_rate = int(input_stream.rate or input_stream.codec_context.sample_rate or 44_100)
        output_rate = min(max(input_rate, 8_000), 48_000)

        with av.open(str(destination), mode="w", format="mp4") as output_container:
            for key, value in tags.items():
                output_container.metadata[key] = value
            output_stream = output_container.add_stream("aac", rate=output_rate)
            output_stream.bit_rate = AAC_BITRATE
            output_stream.layout = output_layout
            resampler = av.AudioResampler(
                format="fltp", layout=output_layout, rate=output_rate
            )

            def write_frames(frames: list[Any]) -> None:
                for frame in frames:
                    for packet in output_stream.encode(frame):
                        output_container.mux(packet)

            for frame in input_container.decode(input_stream):
                write_frames(resampler.resample(frame))
            write_frames(resampler.resample(None))
            for packet in output_stream.encode(None):
                output_container.mux(packet)
    _write_mp4_tags(destination, tags)


def _new_temp_file(parent: Path) -> Path:
    handle, name = tempfile.mkstemp(prefix=".mission-control-walkman-", suffix=".tmp", dir=parent)
    os.close(handle)
    return Path(name)


def _remove_stale_temp_files(root: Path) -> None:
    for path in root.rglob(".mission-control-walkman-*.tmp"):
        if path.is_file() and not path.is_symlink():
            try:
                if path.resolve(strict=True).is_relative_to(root):
                    path.unlink(missing_ok=True)
            except OSError:
                continue


def _is_no_space_error(error: OSError) -> bool:
    return error.errno in {28, 39, 112}  # ENOSPC / Windows ERROR_DISK_FULL


def _friendly_error(error: BaseException, relative: Path | None = None) -> str:
    detail = str(error).strip() or error.__class__.__name__
    if relative is not None:
        return f"{relative.as_posix()} : {detail[:240]}"
    return detail[:400]


def synchronize(
    library_dir: Path,
    tele_dir: Path,
    walkman_dir: Path,
    *,
    encoder: Callable[[Path, Path], None] | None = None,
    free_space: Callable[[Path], int] | None = None,
    reserve_bytes: int = FREE_SPACE_RESERVE,
) -> dict[str, Any]:
    """Synchronise les sources en conservant l'arbre et sans jamais supprimer les sources."""
    encoder = encoder or encode_to_aac
    free_space = free_space or (lambda path: shutil.disk_usage(path).free)
    first_file_error: str | None = None

    try:
        library, tele, target = validate_roots(library_dir, tele_dir, walkman_dir)
        sources = [(0, library, _list_audio(library)), (1, tele, _list_audio(tele))]
        candidates: list[tuple[int, Path, Path, Path]] = []
        primary_keys: set[str] = set()
        for source_rank, _root, files in sources:
            for source, relative in files:
                output_relative = _destination_relative(relative)
                key = _path_key(output_relative)
                if source_rank == 0:
                    if key in primary_keys:
                        # Le premier chemin A→Z de la bibliothèque est déterministe.
                        candidates.append((source_rank, source, relative, output_relative))
                        continue
                    primary_keys.add(key)
                candidates.append((source_rank, source, relative, output_relative))

        _update(n_total=sum(len(files) for _, _, files in sources), phase="copying", current_file=None)
        _remove_stale_temp_files(target)
        destination_index = _existing_files(target)
        selected_outputs: set[str] = set()
        for source_rank, source, relative, output_relative in candidates:
            source_suffix = source.suffix.lower()
            is_conversion = source_suffix in {".flac", ".dsf"}
            key = _path_key(output_relative)
            current_name = relative.as_posix()
            _update(
                phase="converting" if is_conversion else "copying",
                current_file=current_name,
            )

            try:
                if source_rank == 1 and key in primary_keys:
                    _increment("skipped_priority")
                    continue
                if key in selected_outputs:
                    _increment("skipped_priority")
                    continue
                destination = _safe_destination(target, output_relative)
                existing = destination_index.get(key)
                if existing is None and destination.exists():
                    existing = destination
                if (
                    not is_conversion
                    and existing is not None
                    and existing.is_file()
                    and _hash(source) == _hash(existing)
                ):
                    selected_outputs.add(key)
                    _increment("identical")
                    continue
                estimated_size = estimate_output_size(source)
                if free_space(target) < estimated_size + reserve_bytes:
                    _increment("skipped_capacity")
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                temp_path = _new_temp_file(destination.parent)
                try:
                    if is_conversion:
                        encoder(source, temp_path)
                    else:
                        shutil.copy2(source, temp_path)

                    if free_space(target) < reserve_bytes:
                        _increment("skipped_capacity")
                        continue
                    if existing is not None and existing.is_file() and _hash(temp_path) == _hash(existing):
                        _increment("identical")
                        selected_outputs.add(key)
                        continue

                    replacing = existing is not None and existing.is_file()
                    final_path = existing if replacing else destination
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(temp_path, final_path)
                    temp_path = None
                    destination_index[key] = final_path
                    selected_outputs.add(key)
                    if replacing:
                        _increment("replaced")
                        if is_conversion:
                            _increment("converted")
                    elif is_conversion:
                        _increment("converted")
                    else:
                        _increment("copied")
                finally:
                    if temp_path is not None:
                        temp_path.unlink(missing_ok=True)
            except OSError as error:
                if _is_no_space_error(error):
                    _increment("skipped_capacity")
                    continue
                _increment("failed")
                first_file_error = first_file_error or _friendly_error(error, relative)
                if not target.is_dir():
                    raise RuntimeError("Le Walkman a été déconnecté pendant la synchronisation.") from error
            except Exception as error:
                _increment("failed")
                first_file_error = first_file_error or _friendly_error(error, relative)
            finally:
                with _LOCK:
                    _PROGRESS["n_done"] += 1
                    _PROGRESS["current_file"] = None
                _publish_progress()

        _update(
            active=False,
            status="completed",
            phase=None,
            current_file=None,
            error=first_file_error,
        )
    except Exception as error:
        _update(
            active=False,
            status="failed",
            phase=None,
            current_file=None,
            error=_friendly_error(error),
        )
    return get_progress()
