"""Configuration logging — texte lisible (défaut) ou JSON structuré.

Active le format JSON via ``LOG_FORMAT=json`` (variable d'env) pour faciliter
l'agrégation par un collecteur de logs.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys

from app.core.config import settings

_TEXT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s :: %(message)s"
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}


def configure_utf8_standard_streams() -> None:
    """Empêche une sortie Unicode de faire tomber un traitement sous Windows.

    Quand Uvicorn est lancé par ``concurrently``, Python peut conserver la page de
    codes Windows pour stdout/stderr. Un simple ``print`` contenant, par exemple,
    un delta grec ou un nom de fonds non latin levait alors ``UnicodeEncodeError``
    jusque dans l'optimiseur. Les flux de capture utilisés par les tests ne
    proposent pas nécessairement ``reconfigure`` : ils sont volontairement
    ignorés.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (AttributeError, OSError, ValueError):
                # Flux fermé, remplacé ou non reconfigurable : le logger reste
                # utilisable et l'appelant n'a pas à connaître ce détail.
                continue


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
    configure_utf8_standard_streams()
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
    # httpx journalise chaque requête au niveau INFO. Les intégrations externes
    # peuvent en produire plusieurs dizaines au démarrage ; les avertissements
    # applicatifs restent journalisés, mais les succès/redirects HTTP ne polluent
    # plus la sortie standard. Le niveau DEBUG conserve ce détail pour diagnostiquer.
    if level >= logging.INFO:
        for logger_name in ("httpx", "httpcore"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)
