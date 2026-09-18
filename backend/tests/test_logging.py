from __future__ import annotations


def test_configure_utf8_standard_streams_reconfigures_both(monkeypatch):
    from app.core import logging as app_logging

    class Stream:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def reconfigure(self, **kwargs: str) -> None:
            self.calls.append(kwargs)

    stdout = Stream()
    stderr = Stream()
    monkeypatch.setattr(app_logging.sys, "stdout", stdout)
    monkeypatch.setattr(app_logging.sys, "stderr", stderr)

    app_logging.configure_utf8_standard_streams()

    expected = [{"encoding": "utf-8", "errors": "backslashreplace"}]
    assert stdout.calls == expected
    assert stderr.calls == expected


def test_configure_utf8_standard_streams_accepts_capture_streams(monkeypatch):
    from app.core import logging as app_logging

    monkeypatch.setattr(app_logging.sys, "stdout", object())
    monkeypatch.setattr(app_logging.sys, "stderr", object())

    app_logging.configure_utf8_standard_streams()
