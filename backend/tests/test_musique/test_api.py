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


def test_ambiances_and_membership_and_export():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T", duree_sec=100)); s.commit()
    client = _client(engine)

    assert client.get("/musique/ambiances").status_code == 200
    r = client.put("/musique/tracks/1/ambiances/café")
    assert r.status_code == 204
    pl = client.get("/musique/playlists/café")
    assert pl.status_code == 200 and len(pl.json()) == 1
    m = client.get("/musique/playlists/café/export.m3u")
    assert m.status_code == 200 and m.text.startswith("#EXTM3U")
    assert client.delete("/musique/tracks/1/ambiances/café").status_code == 204
    assert client.get("/musique/playlists/café").json() == []


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
