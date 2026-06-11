"""Tests du classement par lots via l'API Claude (claude_client)."""
import json

from app.services.musique import claude_client
from app.services.musique.constants import AMBIANCE_NAMES


class _FakeBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _FakeResp:
    def __init__(self, payload: dict):
        self.content = [_FakeBlock(json.dumps(payload))]


def test_is_configured_depends_on_api_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert claude_client.is_configured() is False
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-xxx")
    assert claude_client.is_configured() is True


def test_build_batch_prompt_contains_tracks_and_ambiances():
    tracks = [
        {"artist": "Joe Hisaishi", "album": "Spirited Away", "title": "One Summer's Day", "genre": "BO"},
        {"artist": "Daft Punk", "album": "Discovery", "title": "One More Time", "genre": "Électro"},
    ]
    p = claude_client.build_batch_prompt(tracks)
    assert "café" in p and "love" in p          # les ambiances et leurs définitions
    assert "One Summer's Day" in p and "Daft Punk" in p
    assert "1." in p and "2." in p              # morceaux numérotés (index 1-based)


def test_classify_batch_parses_structured_response():
    tracks = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    payload = {"resultats": [
        {"index": 1, "ambiances": ["café", "repos"]},
        {"index": 2, "ambiances": []},               # traité mais aucune ambiance
        {"index": 3, "ambiances": ["soirée"]},
    ]}
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeResp(payload)

    res = claude_client.classify_batch(tracks, _create=fake_create)
    assert res == [["café", "repos"], [], ["soirée"]]
    # Le schéma JSON contraint la sortie (pas de texte libre)
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert "max_tokens" in captured


def test_classify_batch_ignores_unknown_ambiances_and_indexes():
    tracks = [{"title": "A"}]
    payload = {"resultats": [
        {"index": 1, "ambiances": ["café", "inconnu", "café"]},
        {"index": 99, "ambiances": ["love"]},        # index hors lot : ignoré
    ]}
    res = claude_client.classify_batch(tracks, _create=lambda **kw: _FakeResp(payload))
    assert res == [["café"]]
    assert all(a in AMBIANCE_NAMES for ambs in res for a in ambs)
