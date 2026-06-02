"""Configuration logging — texte lisible (défaut) ou JSON structuré.

Active le format JSON via ``LOG_FORMAT=json`` (variable d'env) pour faciliter
l'agrégation par un collecteur de logs.
"""

from __future__ import annotations

import datetime as dt
import json
import logging

from app.core.config import settings

_TEXT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s :: %(message)s"
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Sérialise chaque enregistrement de log en une ligne JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": dt.datetime.fromtimestamp(record.created, dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Champs supplémentaires passés via logger.x(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging() -> None:
    level = getattr(logging, settings.app_log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT, datefmt="%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    # Remplace les handlers existants pour éviter les doublons (reconfiguration).
    root.handlers = [handler]
