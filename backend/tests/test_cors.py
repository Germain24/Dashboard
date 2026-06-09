"""CORS restreint (#191) : méthodes/headers explicites, origines réelles."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

ORIGIN = "http://localhost:3000"


def test_preflight_methods_are_explicit_not_wildcard():
    client = TestClient(app)
    r = client.options("/health", headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "DELETE",
    })
    allow = r.headers.get("access-control-allow-methods", "")
    assert allow != "*"
    assert "DELETE" in allow
    assert "GET" in allow
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_disallowed_origin_gets_no_cors_header():
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert r.headers.get("access-control-allow-origin") is None


def test_pagination_headers_are_exposed():
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": ORIGIN})
    expose = r.headers.get("access-control-expose-headers", "")
    assert "X-Total-Count" in expose
