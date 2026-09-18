"""Pagination standardisée (limit/offset) — rétro-compatible.

Le corps de réponse reste un tableau JSON simple (le frontend n'a rien à
changer) ; le nombre total d'éléments est exposé dans l'en-tête
``X-Total-Count`` (et la fenêtre dans ``Content-Range``).

Usage dans une route ::

    from app.core.pagination import Pagination, paginate

    @router.get("/transactions")
    def list_tx(response: Response, page: Pagination = Depends(),
                session: Session = Depends(get_session)):
        stmt = select(Transaction).order_by(Transaction.date.desc())
        return paginate(session, stmt, response, page)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Query, Response
from sqlalchemy import func
from sqlmodel import Session, select


@dataclass
class Pagination:
    """Dépendance FastAPI : ``?limit=&offset=``."""

    limit: int = Query(default=100, ge=1, le=1000)
    offset: int = Query(default=0, ge=0)


def paginate(session: Session, statement, response: Response, page: Pagination) -> list[Any]:
    """Applique offset/limit, renseigne X-Total-Count + Content-Range, renvoie la page."""
    # Total avant pagination (sous-requête du statement filtré).
    total = session.exec(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).one()
    rows = list(session.exec(statement.offset(page.offset).limit(page.limit)).all())

    response.headers["X-Total-Count"] = str(total)
    start = page.offset
    end = page.offset + len(rows) - 1 if rows else page.offset
    response.headers["Content-Range"] = f"items {start}-{end}/{total}"
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, Content-Range"
    return rows
