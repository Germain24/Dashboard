from app.services.musique.classify import (
    build_batch_prompt,
    build_prompt,
    classify_untagged,
    parse_ambiances,
    parse_batch_response,
)
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


def test_classify_reprend_les_classes_sans_ambiance():
    """Auto-guérison : un morceau marqué classé mais SANS ambiance (vieux run
    raté) est repris par le classement, sans bouton Réinitialiser."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", title="T1", classified=True))  # raté : sans ambiance
        s.add(MusicTrack(path="B/2.flac", title="T2", classified=True))  # ok : a une ambiance
        s.commit()
        s.add(TrackAmbiance(track_id=2, ambiance="café", source="auto"))
        s.commit()

        res = classify_untagged(s, generate=lambda prompt, **kw: "1: énergie")
        assert res["total"] == 1, "seul le morceau sans ambiance doit être repris"
        ambs = {(ta.track_id, ta.ambiance) for ta in s.exec(select(TrackAmbiance)).all()}
        assert (1, "énergie") in ambs


def test_build_batch_prompt_numbers_tracks():
    p = build_batch_prompt([
        {"artist": "A", "album": "X", "title": "T1", "genre": ""},
        {"artist": "B", "album": "Y", "title": "T2", "genre": "jazz"},
    ])
    assert "1." in p and "2." in p and "T1" in p and "T2" in p
    assert "café" in p  # la liste des ambiances reste présente


def test_parse_batch_response_maps_numbers():
    raw = "1: café, étude\n2 : aucune\n3- énergie"
    out = parse_batch_response(raw, 3, AMBIANCE_NAMES)
    assert out == {1: ["café", "étude"], 2: [], 3: ["énergie"]}


def test_parse_batch_response_missing_number_is_absent():
    """Un numéro absent de la réponse = morceau non traité (sera retenté)."""
    out = parse_batch_response("1: café", 2, AMBIANCE_NAMES)
    assert 1 in out and 2 not in out


def test_parse_batch_response_single_track_fallback():
    """Lot de 1 : si le modèle répond sans numéro, on prend la réponse brute."""
    assert parse_batch_response("café, étude", 1, AMBIANCE_NAMES) == {1: ["café", "étude"]}


def test_classify_batches_calls(monkeypatch):
    """560 morceaux ≠ 560 appels Ollama : les morceaux partent par lots."""
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    calls = []

    def fake_generate(prompt, **kw):
        calls.append(prompt)
        # Réponse numérotée pour tous les morceaux du lot.
        import re
        nums = re.findall(r"^(\d+)\.", prompt, flags=re.MULTILINE)
        return "\n".join(f"{n}: café" for n in nums)

    with Session(engine) as s:
        for i in range(20):
            s.add(MusicTrack(path=f"A/{i}.flac", title=f"T{i}"))
        s.commit()
        res = classify_untagged(s, generate=fake_generate)
        assert res["classes"] == 20
        assert len(calls) < 20, f"attendu des lots, mais {len(calls)} appels pour 20 morceaux"


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
