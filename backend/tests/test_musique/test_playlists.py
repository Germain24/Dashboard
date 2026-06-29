from app.services.musique.playlists import reco_bibliotheque, to_m3u


def test_set_membership_add_remove():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.playlists import set_membership

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac")); s.commit()
        set_membership(s, 1, "café", True)
        set_membership(s, 1, "café", True)  # idempotent
        assert len(s.exec(select(TrackAmbiance)).all()) == 1
        set_membership(s, 1, "café", False)
        assert s.exec(select(TrackAmbiance)).all() == []


def test_set_membership_rejects_unknown_ambiance():
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack
    from app.services.musique.playlists import set_membership
    import pytest

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac")); s.commit()
        with pytest.raises(ValueError):
            set_membership(s, 1, "inexistante", True)


def test_parse_suggestions_splits_list():
    from app.services.musique.discovery import parse_suggestions
    assert parse_suggestions("- Artiste A\n- Artiste B\n") == ["Artiste A", "Artiste B"]
    assert parse_suggestions("1. X\n2. Y") == ["X", "Y"]


def test_to_m3u_relative_paths():
    tracks = [
        {"path": "A/Alb/01.flac", "artist": "A", "title": "T1", "duree_sec": 200},
        {"path": "B/Alb/02.mp3", "artist": "B", "title": "T2", "duree_sec": None},
    ]
    m = to_m3u(tracks)
    lines = m.splitlines()
    assert lines[0] == "#EXTM3U"
    assert "#EXTINF:200,A - T1" in lines
    assert "A/Alb/01.flac" in lines
    assert "#EXTINF:-1,B - T2" in lines  # durée inconnue -> -1


def test_reco_scores_by_shared_artist_or_genre():
    tracks_in = [{"id": 1, "artist": "X", "genre": "jazz"}]
    tracks_out = [
        {"id": 2, "artist": "X", "genre": "rock"},   # même artiste -> score 1
        {"id": 3, "artist": "Z", "genre": "jazz"},   # même genre -> score 1
        {"id": 4, "artist": "Q", "genre": "metal"},  # rien -> exclu
    ]
    reco = reco_bibliotheque(tracks_in, tracks_out)
    ids = [t["id"] for t in reco]
    assert set(ids) == {2, 3} and 4 not in ids


def test_purge_unknown_ambiances():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.playlists import purge_unknown_ambiances

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", classified=True))   # id1 : ancien nom -> purgé
        s.add(MusicTrack(path="B/2.flac", classified=True))   # id2 : slug valide -> conservé
        s.commit()
        s.add(TrackAmbiance(track_id=1, ambiance="café", source="auto"))      # ancien nom
        s.add(TrackAmbiance(track_id=2, ambiance="sport-gym", source="auto"))  # slug valide
        s.commit()

        n = purge_unknown_ambiances(s)
        assert n == 1
        restantes = {ta.ambiance for ta in s.exec(select(TrackAmbiance)).all()}
        assert restantes == {"sport-gym"}
        t1 = s.exec(select(MusicTrack).where(MusicTrack.path == "A/1.flac")).first()
        t2 = s.exec(select(MusicTrack).where(MusicTrack.path == "B/2.flac")).first()
        assert t1.classified is False   # orphelin -> à reclasser
        assert t2.classified is True


def test_purge_unknown_ambiances_idempotent():
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    from app.services.musique.playlists import purge_unknown_ambiances

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        assert purge_unknown_ambiances(s) == 0
