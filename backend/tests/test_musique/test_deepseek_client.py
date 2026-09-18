"""Tests du classement par lots via l'API DeepSeek (deepseek_client)."""
import json

from app.services.musique import deepseek_client
from app.services.musique.constants import AMBIANCE_NAMES


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = {"choices": [{"message": {"content": json.dumps(payload)}}]}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_is_configured_depends_on_api_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "deepseek_api_key", "")
    assert deepseek_client.is_configured() is False
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-xxx")
    assert deepseek_client.is_configured() is True


def test_build_batch_prompt_contains_tracks_labels_and_json():
    tracks = [
        {"artist": "Daft Punk", "album": "Discovery", "title": "One More Time", "genre": "Électro"},
    ]
    p = deepseek_client.build_batch_prompt(tracks)
    assert "café pour le petit dep" in p and "amour/love/sex" in p   # labels affichés
    assert "One More Time" in p and "Daft Punk" in p
    assert "JSON" in p and "resultats" in p                          # consigne JSON


def test_classify_batch_convertit_labels_en_slugs():
    tracks = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    payload = {"resultats": [
        {"index": 1, "ambiances": ["café pour le petit dep", "Mélancolie"]},
        {"index": 2, "ambiances": []},
        {"index": 3, "ambiances": ["soirée ( internationale )"]},
    ]}
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["model"] = json["model"]
        captured["response_format"] = json["response_format"]
        return _FakeResp(payload)

    res = deepseek_client.classify_batch(tracks, _post=fake_post)
    assert res == [["cafe-petit-dej", "melancolie"], [], ["soiree-internationale"]]
    assert captured["url"].endswith("/chat/completions")
    assert captured["response_format"] == {"type": "json_object"}


def test_classify_batch_ignore_labels_inconnus_et_index_hors_lot():
    tracks = [{"title": "A"}]
    payload = {"resultats": [
        {"index": 1, "ambiances": ["café pour le petit dep", "inconnu", "café pour le petit dep"]},
        {"index": 99, "ambiances": ["amour/love/sex"]},
    ]}
    res = deepseek_client.classify_batch(tracks, _post=lambda url, **kw: _FakeResp(payload))
    assert res == [["cafe-petit-dej"]]
    assert all(a in AMBIANCE_NAMES for ambs in res for a in ambs)
