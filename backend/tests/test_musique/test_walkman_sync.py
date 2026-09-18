from __future__ import annotations

import wave
from pathlib import Path

from app.services.musique import walkman_sync


def _roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    library = tmp_path / "library"
    tele = tmp_path / "tele"
    walkman = tmp_path / "walkman"
    library.mkdir()
    tele.mkdir()
    walkman.mkdir()
    return library, tele, walkman


def _write(root: Path, relative: str, contents: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    return path


def test_sync_preserves_library_priority_replaces_changes_and_skips_identical(tmp_path: Path):
    library, tele, walkman = _roots(tmp_path)
    _write(library, "Artist/Album/A.mp3", b"library version")
    _write(tele, "Artist/Album/A.mp3", b"tele version")
    _write(tele, "Artist/Album/B.mp3", b"same bytes")
    _write(walkman, "Artist/Album/A.mp3", b"old version")
    _write(walkman, "Artist/Album/B.mp3", b"same bytes")
    walkman_sync.begin_sync()

    result = walkman_sync.synchronize(
        library,
        tele,
        walkman,
        free_space=lambda _path: 1_000_000_000,
        reserve_bytes=0,
    )

    assert (walkman / "Artist/Album/A.mp3").read_bytes() == b"library version"
    assert (walkman / "Artist/Album/B.mp3").read_bytes() == b"same bytes"
    assert result["status"] == "completed"
    assert result["replaced"] == 1
    assert result["identical"] == 1
    assert result["skipped_priority"] == 1
    assert result["failed"] == 0
    assert (tele / "Artist/Album/A.mp3").read_bytes() == b"tele version"

    walkman_sync.begin_sync()
    repeated = walkman_sync.synchronize(
        library,
        tele,
        walkman,
        free_space=lambda _path: 0,
        reserve_bytes=0,
    )
    assert repeated["identical"] == 2
    assert repeated["copied"] == repeated["replaced"] == 0


def test_sync_skips_oversized_track_but_continues_in_alphabetical_order(tmp_path: Path):
    library, tele, walkman = _roots(tmp_path)
    _write(library, "Artist/Album/A.mp3", b"too big")
    _write(library, "Artist/Album/B.mp3", b"ok")
    walkman_sync.begin_sync()

    def remaining_bytes(target: Path) -> int:
        used = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
        return 5 - used

    result = walkman_sync.synchronize(
        library,
        tele,
        walkman,
        free_space=remaining_bytes,
        reserve_bytes=0,
    )

    assert not (walkman / "Artist/Album/A.mp3").exists()
    assert (walkman / "Artist/Album/B.mp3").read_bytes() == b"ok"
    assert result["skipped_capacity"] == 1
    assert result["copied"] == 1
    assert result["n_done"] == result["n_total"] == 2


def test_identical_mp3_is_skipped_even_when_no_new_space_is_available(tmp_path: Path):
    library, tele, walkman = _roots(tmp_path)
    _write(library, "Artist/Album/Song.mp3", b"already on player")
    _write(walkman, "Artist/Album/Song.mp3", b"already on player")
    walkman_sync.begin_sync()

    result = walkman_sync.synchronize(
        library,
        tele,
        walkman,
        free_space=lambda _path: 0,
        reserve_bytes=0,
    )

    assert result["identical"] == 1
    assert result["skipped_capacity"] == 0
    assert result["status"] == "completed"


def test_sync_converts_lossless_formats_and_keeps_artist_album_track_tree(
    tmp_path: Path, monkeypatch
):
    library, tele, walkman = _roots(tmp_path)
    source = _write(library, "Artist/Album/Track.flac", b"synthetic flac")
    monkeypatch.setattr(walkman_sync, "_duration_seconds", lambda _path: 1.0)
    walkman_sync.begin_sync()

    def fake_encoder(input_path: Path, output_path: Path) -> None:
        output_path.write_bytes(b"AAC320:" + input_path.read_bytes())

    result = walkman_sync.synchronize(
        library,
        tele,
        walkman,
        encoder=fake_encoder,
        free_space=lambda _path: 1_000_000_000,
        reserve_bytes=0,
    )

    output = walkman / "Artist/Album/Track.m4a"
    assert output.read_bytes() == b"AAC320:synthetic flac"
    assert not (walkman / "Artist/Album/Track.flac").exists()
    assert result["converted"] == 1
    assert source.read_bytes() == b"synthetic flac"


def test_encode_to_aac_writes_playable_m4a_and_preserves_mp4_tags(tmp_path: Path):
    import mutagen
    from mutagen.mp4 import MP4

    source = tmp_path / "tone.wav"
    output = tmp_path / "tone.m4a"
    sample_rate = 44_100
    frames = b"\0\0" * (sample_rate // 4)
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(frames)

    walkman_sync.encode_to_aac(source, output)
    walkman_sync._write_mp4_tags(
        output,
        {"title": "Titre test", "artist": "Artiste", "album": "Album", "tracknumber": "2/8"},
    )
    converted = mutagen.File(output, easy=True)

    assert converted is not None
    assert converted.info.length > 0
    assert converted.info.sample_rate == sample_rate
    assert isinstance(converted, MP4)
    assert converted["title"] == ["Titre test"]
    assert converted["artist"] == ["Artiste"]
    assert converted["album"] == ["Album"]
    assert converted["tracknumber"] == ["2/8"]
