"""Masquage des secrets + état des intégrations (#192)."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.secrets import integration_status, mask_secret


def test_mask_absent():
    assert mask_secret("") == "(absent)"
    assert mask_secret(None) == "(absent)"


def test_mask_short_secret_fully_hidden():
    assert mask_secret("abcd") == "••••"  # trop court -> rien révélé


def test_mask_long_secret_shows_ends_only():
    masked = mask_secret("sk-ant-0123456789abcdef")
    assert masked.startswith("sk-a")
    assert masked.endswith("cdef")
    assert "0123456789" not in masked


def test_integration_status_presence_only():
    s = SimpleNamespace(
        google_client_id="x", google_client_secret="y", google_refresh_token="z",
        ical_sync_url_list=["https://a.ics"],
        anthropic_api_key="",
    )
    st = integration_status(s)
    assert st == {"google_calendar": True, "ical_sync": True, "anthropic": False}
