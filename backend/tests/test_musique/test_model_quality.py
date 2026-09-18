def test_music_track_a_les_colonnes_qualite():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", bitrate_kbps=940, sample_rate_hz=44100,
                         bits_per_sample=16, qobuz_available=True))
        s.commit()
        t = s.exec(select(MusicTrack)).first()
        assert t.bitrate_kbps == 940 and t.sample_rate_hz == 44100
        assert t.bits_per_sample == 16 and t.qobuz_available is True


def test_colonnes_qualite_par_defaut_none():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/2.mp3")); s.commit()
        t = s.exec(select(MusicTrack)).first()
        assert t.bitrate_kbps is None and t.qobuz_available is None
