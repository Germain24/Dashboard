"""Démarrage automatique d'Ollama au lancement du backend."""

from app.services.musique import ollama_client as oc


class _Resp:
    def __init__(self, code):
        self.status_code = code


def test_is_running_true_on_200():
    assert oc.is_running("http://h", _get=lambda url, timeout=0: _Resp(200)) is True


def test_is_running_false_on_error():
    def boom(url, timeout=0):
        raise ConnectionError("refused")
    assert oc.is_running("http://h", _get=boom) is False


def test_ensure_running_noop_when_already_up():
    calls = []
    ok = oc.ensure_running("http://h", is_running_fn=lambda h: True,
                           popen=lambda *a, **k: calls.append(a), sleep=lambda s: None)
    assert ok is True
    assert calls == []  # ne lance pas un 2e serveur


def test_ensure_running_starts_then_waits():
    state = {"up": False}
    launched = []

    def fake_popen(*a, **k):
        launched.append(a[0])
        state["up"] = True  # le serveur démarre
        return object()

    ok = oc.ensure_running(
        "http://h",
        is_running_fn=lambda h: state["up"],
        popen=fake_popen,
        sleep=lambda s: None,
        attempts=3,
    )
    assert ok is True
    assert launched and launched[0][0] == "ollama"  # a lancé `ollama serve`


def test_ensure_running_false_when_ollama_absent():
    def missing(*a, **k):
        raise FileNotFoundError("ollama")
    ok = oc.ensure_running("http://h", is_running_fn=lambda h: False,
                           popen=missing, sleep=lambda s: None, attempts=2)
    assert ok is False
