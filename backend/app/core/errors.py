"""Gestion d'erreurs centralisée — réponses JSON uniformes {code, detail}.

Toutes les exceptions remontées par l'API sont sérialisées dans la même
enveloppe : ``{"code": <int>, "detail": <str>, "errors": <optionnel>}``.
Cela permet au frontend de traiter les erreurs de façon homogène.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


def _payload(code: int, detail, errors=None) -> dict:
    body: dict = {"code": code, "detail": detail}
    if errors is not None:
        body["errors"] = errors
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Enregistre les handlers d'exception globaux sur l'application."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.status_code, exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_payload(422, "Validation error", errors=exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        log.exception("Erreur non gérée sur %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_payload(500, "Erreur interne du serveur"),
        )
