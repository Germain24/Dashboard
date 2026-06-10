"""Client Ollama minimal (génération non-stream). Aucun chat persistant."""
from __future__ import annotations

import httpx

from app.core.config import settings


def generate(prompt: str, *, host: str | None = None, model: str | None = None,
             _post=httpx.post) -> str:
    host = host or settings.musique_ollama_host
    model = model or settings.musique_ollama_model
    resp = _post(f"{host}/api/generate",
                 json={"model": model, "prompt": prompt, "stream": False}, timeout=120.0)
    resp.raise_for_status()
    return resp.json().get("response", "")
