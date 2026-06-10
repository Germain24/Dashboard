from app.services.musique.classify import build_prompt, classify_untagged, parse_ambiances
from app.services.musique.constants import AMBIANCE_NAMES


def test_parse_ambiances_keeps_valid_only():
    assert parse_ambiances("café, étude", AMBIANCE_NAMES) == ["café", "étude"]
    assert parse_ambiances("Étude.", AMBIANCE_NAMES) == ["étude"]   # accents/casse/ponctuation
    assert parse_ambiances("inconnu", AMBIANCE_NAMES) == []
    assert parse_ambiances("aucune", AMBIANCE_NAMES) == []


def test_build_prompt_lists_ambiances():
    p = build_prompt({"artist": "A", "album": "B", "title": "T", "genre": "jazz"})
    assert "café" in p and "love" in p and "T" in p


def test_classify_untagged_creates_rows(monkeypatch):
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T"))
        s.commit()
        res = classify_untagged(s, generate=lambda prompt, **kw: "café, étude")
        assert res["classes"] == 1
        ambs = {ta.ambiance for ta in s.exec(select(TrackAmbiance)).all()}
        assert ambs == {"café", "étude"}
        t = s.exec(select(MusicTrack)).first()
        assert t.classified is True


def test_classify_failure_does_not_mark_classified():
    """Si Ollama échoue, le morceau reste à reclasser (pas marqué classified)."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.classify import classify_untagged

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def boom(prompt, **kw):
        raise RuntimeError("ollama 500")

    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T")); s.commit()
        res = classify_untagged(s, generate=boom)
        assert res["classes"] == 0
        t = s.exec(select(MusicTrack)).first()
        assert t.classified is False  # réessayable
        assert s.exec(select(TrackAmbiance)).all() == []


def test_reset_classification_targets_empty_only():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.classify import reset_classification

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", classified=True))   # id1 : sans ambiance -> reset
        s.add(MusicTrack(path="B/2.flac", classified=True))   # id2 : avec ambiance -> garde
        s.commit()
        s.add(TrackAmbiance(track_id=2, ambiance="café", source="auto")); s.commit()
        res = reset_classification(s)
        assert res["reinitialises"] == 1
        t1 = s.exec(select(MusicTrack).where(MusicTrack.path == "A/1.flac")).first()
        t2 = s.exec(select(MusicTrack).where(MusicTrack.path == "B/2.flac")).first()
        assert t1.classified is False and t2.classified is True
