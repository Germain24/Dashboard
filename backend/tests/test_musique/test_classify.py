from app.services.musique.classify import build_prompt, classify_untagged, parse_ambiances
from app.services.musique.constants import AMBIANCE_NAMES


def test_parse_ambiances_keeps_valid_only():
    assert parse_ambiances("café, étude", AMBIANCE_NAMES) == ["café", "étude"]
    assert parse_ambiances("Étude.", AMBIANCE_NAMES) == ["étude"]   # accents/casse/ponctuation
    assert parse_ambiances("inconnu", AMBIANCE_NAMES) == []
    assert parse_ambiances("aucune", AMBIANCE_NAMES) == []


def test_parse_ambiances_accepte_les_synonymes():
    """Le modèle répond souvent en français libre : « amour » doit compter pour
    « love », « fête » pour « soirée », etc."""
    assert parse_ambiances("amour", AMBIANCE_NAMES) == ["love"]
    assert parse_ambiances("romantique", AMBIANCE_NAMES) == ["love"]
    assert parse_ambiances("fête, dansant", AMBIANCE_NAMES) == ["soirée"]
    assert parse_ambiances("détente", AMBIANCE_NAMES) == ["repos"]
    assert parse_ambiances("concentration", AMBIANCE_NAMES) == ["étude"]
    assert parse_ambiances("amour, énergie", AMBIANCE_NAMES) == ["love", "énergie"]


def test_build_prompt_lists_ambiances():
    p = build_prompt({"artist": "A", "album": "B", "title": "T", "genre": "jazz"})
    assert "café" in p and "love" in p and "T" in p


def test_generate_force_temperature_zero():
    """La classification doit être déterministe : temp 0.8 par défaut d'Ollama
    rendait les attributions aléatoires."""
    from app.services.musique import ollama_client

    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "café"}

    def fake_post(url, json, timeout):
        captured.update(json)
        return FakeResp()

    ollama_client.generate("prompt", _post=fake_post)
    assert captured["options"]["temperature"] == 0


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


def test_classify_ne_reprend_jamais_un_morceau_classe():
    """Un morceau classified=True n'est JAMAIS reclassé — même avec 0 ambiance.
    classified=True + 0 ambiance = « traité, aucune playlist adaptée »."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", title="T1", classified=True))   # traité : 0 ambiance
        s.add(MusicTrack(path="B/2.flac", title="T2", classified=True))   # traité : 1 ambiance
        s.add(MusicTrack(path="C/3.flac", title="T3", classified=False))  # nouveau
        s.commit()
        s.add(TrackAmbiance(track_id=2, ambiance="café", source="auto"))
        s.commit()

        res = classify_untagged(s, generate=lambda prompt, **kw: "énergie")
        assert res["total"] == 1, "seul le nouveau morceau doit être traité"
        ambs = {(ta.track_id, ta.ambiance) for ta in s.exec(select(TrackAmbiance)).all()}
        assert ambs == {(2, "café"), (3, "énergie")}


def test_classify_untagged_par_lots_marque_aussi_les_zero_ambiance():
    """Chemin API Claude (par lots) : tout morceau traité est marqué classified,
    y compris ceux sans aucune ambiance (pour ne jamais les refaire)."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", title="T1"))
        s.add(MusicTrack(path="B/2.flac", title="T2"))
        s.commit()

        res = classify_untagged(s, classify_lot=lambda tracks: [["soirée"], []])
        assert res == {"classes": 1, "total": 2}
        for t in s.exec(select(MusicTrack)).all():
            assert t.classified is True
        ambs = [(ta.track_id, ta.ambiance) for ta in s.exec(select(TrackAmbiance)).all()]
        assert ambs == [(1, "soirée")]


def test_classify_untagged_par_lots_echec_reste_reclassable():
    """Si l'appel API échoue, aucun morceau du lot n'est marqué classé."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def boom(tracks):
        raise RuntimeError("API down")

    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", title="T1")); s.commit()
        res = classify_untagged(s, classify_lot=boom)
        assert res["classes"] == 0
        t = s.exec(select(MusicTrack)).first()
        assert t.classified is False
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


def test_reset_classification_tout_efface_auto_garde_manuel():
    """Reset complet : efface les attributions AUTO (mauvais run) mais préserve
    les ambiances posées à la main, et remet les morceaux à reclasser."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.classify import reset_classification

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", classified=True))  # auto seulement
        s.add(MusicTrack(path="B/2.flac", classified=True))  # auto + manuel
        s.commit()
        s.add(TrackAmbiance(track_id=1, ambiance="repos", source="auto"))
        s.add(TrackAmbiance(track_id=2, ambiance="étude", source="auto"))
        s.add(TrackAmbiance(track_id=2, ambiance="love", source="manuel"))
        s.commit()

        res = reset_classification(s, tout=True)
        assert res["reinitialises"] == 2

        restantes = [(ta.track_id, ta.ambiance, ta.source) for ta in s.exec(select(TrackAmbiance)).all()]
        assert restantes == [(2, "love", "manuel")]
        t1 = s.exec(select(MusicTrack).where(MusicTrack.path == "A/1.flac")).first()
        t2 = s.exec(select(MusicTrack).where(MusicTrack.path == "B/2.flac")).first()
        assert t1.classified is False and t2.classified is False
