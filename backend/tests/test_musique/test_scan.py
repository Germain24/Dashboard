from pathlib import Path

from app.services.musique import scan


def test_relative_to_root_uses_forward_slashes(tmp_path):
    root = tmp_path
    p = tmp_path / "Artiste" / "Album" / "01.flac"
    assert scan.relative_to_root(p, root) == "Artiste/Album/01.flac"


def test_find_cover_prefers_folder_jpg(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    (album / "Folder.jpg").write_bytes(b"x")
    assert scan.find_cover(album) == album / "Folder.jpg"


def test_find_cover_none_when_absent(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    assert scan.find_cover(album) is None


def test_find_cover_fallback_any_image(tmp_path):
    """Pochette au nom quelconque (rip Spotify/web) : on prend la première image."""
    album = tmp_path / "Album"
    album.mkdir()
    (album / "thriller-michael-jackson.jpg").write_bytes(b"x")
    assert scan.find_cover(album) == album / "thriller-michael-jackson.jpg"


def test_find_cover_fallback_ignores_audio(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    (album / "01.flac").write_bytes(b"x")
    assert scan.find_cover(album) is None


def test_find_cover_canonical_name_wins_over_fallback(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    (album / "aaa-random.png").write_bytes(b"x")
    (album / "cover.jpg").write_bytes(b"x")
    assert scan.find_cover(album) == album / "cover.jpg"


def test_scan_library_indexes_audio(tmp_path, monkeypatch):
    # Arborescence factice : 1 morceau flac + une pochette.
    album = tmp_path / "Artiste" / "Album"
    album.mkdir(parents=True)
    (album / "01 - Titre.flac").write_bytes(b"x")
    (album / "Folder.jpg").write_bytes(b"x")
    # mutagen ne lit pas un faux fichier -> on stub extract_metadata.
    monkeypatch.setattr(scan, "extract_metadata", lambda p: {
        "artist": "Artiste", "album": "Album", "title": "Titre", "genre": "", "duree_sec": 200})

    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        res = scan.scan_library(s, tmp_path)
        assert res["ajoutes"] == 1
        from app.models.musique import MusicTrack
        from sqlmodel import select
        t = s.exec(select(MusicTrack)).first()
        assert t.path == "Artiste/Album/01 - Titre.flac"
        assert t.cover == "Artiste/Album/Folder.jpg"
        assert t.title == "Titre"
