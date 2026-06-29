from app.services.musique.playlists import reco_bibliotheque


def test_set_membership_add_remove():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.playlists import set_membership

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac")); s.commit()
        set_membership(s, 1, "sport-gym", True)
        set_membership(s, 1, "sport-gym", True)  # idempotent
        assert len(s.exec(select(TrackAmbiance)).all()) == 1
        set_membership(s, 1, "sport-gym", False)
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


def test_to_m3u8_bom_entete_et_lignes():
    from app.services.musique.playlists import to_m3u8
    tracks = [
        {"path": "A/Alb/01.flac", "artist": "A", "title": "T1", "duree_sec": 200},
        {"path": "B/Alb/02.mp3", "artist": "B", "title": "T2", "duree_sec": None},
    ]
    data = to_m3u8(tracks, titre="café pour le petit dep")
    assert isinstance(data, bytes)
    assert data.startswith("﻿".encode("utf-8"))    # BOM UTF-8
    texte = data.decode("utf-8-sig")
    lines = texte.splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#PLAYLIST:café pour le petit dep"
    assert "#EXTINF:200,A - T1" in lines
    assert "A/Alb/01.flac" in lines
    assert "#EXTINF:-1,B - T2" in lines


def test_to_m3u8_playlist_vide():
    from app.services.musique.playlists import to_m3u8
    data = to_m3u8([], titre="Mélancolie")
    texte = data.decode("utf-8-sig")
    assert texte.splitlines() == ["#EXTM3U", "#PLAYLIST:Mélancolie"]


def test_safe_filename_retire_les_caracteres_interdits():
    from app.services.musique.playlists import safe_filename
    assert safe_filename("amour/love/sex") == "amour - love - sex"
    assert safe_filename("soirée ( internationale )") == "soirée ( internationale )"
    assert safe_filename('a:b*c?"d') == "abcd"


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
