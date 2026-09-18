from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app


def _client(engine):
    def override():
        with Session(engine) as s:
            yield s
    app = create_app()
    app.dependency_overrides[get_session] = override
    from fastapi.testclient import TestClient
    return TestClient(app)


def _engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(e)
    return e


def test_membership_and_playlist_avec_slug():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T", duree_sec=100)); s.commit()
    client = _client(engine)

    assert client.get("/musique/ambiances").status_code == 200
    assert client.put("/musique/tracks/1/ambiances/amour-love-sex").status_code == 204
    pl = client.get("/musique/playlists/amour-love-sex")
    assert pl.status_code == 200 and len(pl.json()) == 1
    assert client.delete("/musique/tracks/1/ambiances/amour-love-sex").status_code == 204
    assert client.get("/musique/playlists/amour-love-sex").json() == []


def test_export_zip_un_seul_fichier_par_playlist():
    import io, zipfile
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        from app.models.musique import TrackAmbiance
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T", duree_sec=100)); s.commit()
        s.add(TrackAmbiance(track_id=1, ambiance="amour-love-sex", source="manuel")); s.commit()
    client = _client(engine)

    r = client.get("/musique/playlists/export.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "playlists-musique.zip" in r.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert len(names) == 8                                  # une entrée par playlist
    assert all(n.endswith(".m3u8") and "/" not in n for n in names)
    assert "amour - love - sex.m3u8" in names
    contenu = zf.read("amour - love - sex.m3u8").decode("utf-8-sig")
    assert contenu.startswith("#EXTM3U")
    assert "A/B/1.flac" in contenu


def test_ambiances_renvoie_slug_label_count():
    engine = _engine()
    client = _client(engine)
    rows = client.get("/musique/ambiances").json()
    assert len(rows) == 8
    first = rows[0]
    assert set(first) == {"ambiance", "label", "count"}
    by_slug = {r["ambiance"]: r for r in rows}
    assert by_slug["amour-love-sex"]["label"] == "amour/love/sex"
    assert by_slug["amour-love-sex"]["count"] == 0


def test_quality_liste_et_statut():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/1.mp3", artist="A", title="MP3", bitrate_kbps=320))
        s.add(MusicTrack(path="B/2.flac", artist="B", title="FLAC",
                         bitrate_kbps=940, sample_rate_hz=44100, bits_per_sample=16))
        s.commit()
    client = _client(engine)

    rows = client.get("/musique/quality").json()
    by_title = {r["title"]: r for r in rows}
    assert by_title["MP3"]["format"] == "mp3"
    assert by_title["MP3"]["status"] == "unknown"          # mp3, dispo inconnue
    assert by_title["MP3"]["quality_label"] == "MP3 (320 kbps)"
    assert by_title["FLAC"]["tier"] == "cd"
    assert by_title["FLAC"]["status"] == "owned"


def test_put_qobuz_available_met_a_jour_le_statut():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/1.mp3", artist="A", title="MP3", bitrate_kbps=320)); s.commit()
    client = _client(engine)

    assert client.put("/musique/tracks/1/qobuz-available", json={"available": True}).status_code == 204
    rows = client.get("/musique/quality").json()
    assert rows[0]["qobuz_available"] is True and rows[0]["status"] == "to_buy"

    assert client.put("/musique/tracks/1/qobuz-available", json={"available": None}).status_code == 204
    assert client.get("/musique/quality").json()[0]["status"] == "unknown"

    assert client.put("/musique/tracks/999/qobuz-available", json={"available": True}).status_code == 404


def test_walkman_sync_route_demarre_le_job_et_expose_son_statut(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.musique import walkman_sync

    library, tele, walkman = tmp_path / "library", tmp_path / "tele", tmp_path / "walkman"
    library.mkdir()
    tele.mkdir()
    walkman.mkdir()
    monkeypatch.setattr(settings, "music_dir", str(library))
    monkeypatch.setattr(settings, "music_tele_dir", str(tele))
    monkeypatch.setattr(settings, "walkman_dir", str(walkman))
    monkeypatch.setattr(walkman_sync, "validate_encoder", lambda: None)

    response = _client(_engine()).post("/musique/walkman/sync")

    assert response.status_code == 202
    assert response.json() == {"message": "Synchronisation du Walkman démarrée"}
    status = _client(_engine()).get("/musique/walkman/sync/status").json()
    assert status["active"] is False
    assert status["status"] == "completed"
    assert status["n_done"] == status["n_total"] == 0


def test_walkman_sync_refuse_une_destination_absente(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.musique import walkman_sync

    library, tele = tmp_path / "library", tmp_path / "tele"
    library.mkdir()
    tele.mkdir()
    monkeypatch.setattr(settings, "music_dir", str(library))
    monkeypatch.setattr(settings, "music_tele_dir", str(tele))
    monkeypatch.setattr(settings, "walkman_dir", str(tmp_path / "missing-walkman"))
    monkeypatch.setattr(walkman_sync, "validate_encoder", lambda: None)

    response = _client(_engine()).post("/musique/walkman/sync")

    assert response.status_code == 503
    assert "Walkman est absent" in response.json()["detail"]
    assert walkman_sync.get_progress()["active"] is False
