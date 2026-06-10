"""Client Ollama minimal (génération non-stream) + démarrage auto. Aucun chat."""
from __future__ import annotations

import subprocess
import sys
import time

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


def is_running(host: str | None = None, *, _get=httpx.get) -> bool:
    """True si le serveur Ollama répond sur /api/tags (sinon False, sans lever)."""
    host = host or settings.musique_ollama_host
    try:
        return _get(f"{host}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


def _detached_kwargs() -> dict:
    """Flags pour détacher `ollama serve` du process backend (multi-plateforme)."""
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        return {"creationflags": 0x00000008 | 0x00000200}
    return {"start_new_session": True}


def ensure_running(host: str | None = None, *, is_running_fn=is_running,
                   popen=subprocess.Popen, sleep=time.sleep, attempts: int = 10,
                   force_cpu: bool | None = None) -> bool:
    """Démarre `ollama serve` s'il n'est pas déjà actif. Retourne True si prêt.

    Ne lève jamais : si Ollama n'est pas installé (FileNotFoundError) ou ne démarre
    pas, retourne False (le module musique reste utilisable sans classement).
    Si ``force_cpu`` (défaut = settings), lance avec OLLAMA_LLM_LIBRARY=cpu pour
    éviter le crash du backend GPU/Vulkan sur certaines machines.
    """
    import os

    host = host or settings.musique_ollama_host
    if is_running_fn(host):
        return True
    cpu = settings.musique_ollama_force_cpu if force_cpu is None else force_cpu
    env = {**os.environ, "OLLAMA_LLM_LIBRARY": "cpu"} if cpu else None
    try:
        popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, env=env, **_detached_kwargs())
    except FileNotFoundError:
        return False
    except Exception:
        return False
    for _ in range(attempts):
        sleep(1.0)
        if is_running_fn(host):
            return True
    return False
