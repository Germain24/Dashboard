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
