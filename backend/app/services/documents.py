"""Service Documents/Administratif (#548)."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
import json

from sqlmodel import Session, select

from app.models.documents import Document


def classify_expiry(date: dt.date | None) -> str:
    """Classe l'état d'expiration d'un document."""
    if date is None:
        return "no_date"
    today = dt.date.today()
    if date < today:
        return "expired"
    if (date - today).days <= 30:
        return "warning"
    return "ok"


def get_documents(
    session: Session,
    type: str | None = None,
    q: str | None = None,
) -> list[Document]:
    stmt = select(Document)
    if type:
        stmt = stmt.where(Document.type == type)
    if q:
        term = f"%{q.lower()}%"
        stmt = stmt.where(
            Document.titre.ilike(term) | Document.organisme.ilike(term)
        )
    return list(session.exec(stmt.order_by(Document.date_expiration.asc().nullslast())).all())


def create_document(session: Session, **data) -> Document:
    tags = data.get("tags", [])
    if isinstance(tags, list):
        data["tags"] = json.dumps(tags, ensure_ascii=False)
    doc = Document(**data)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def update_document(session: Session, doc_id: int, patch: dict) -> Document | None:
    doc = session.get(Document, doc_id)
    if not doc:
        return None
    tags = patch.get("tags")
    if isinstance(tags, list):
        patch["tags"] = json.dumps(tags, ensure_ascii=False)
    for k, v in patch.items():
        if hasattr(doc, k):
            setattr(doc, k, v)
    doc.updated_at = utcnow()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def delete_document(session: Session, doc_id: int) -> bool:
    doc = session.get(Document, doc_id)
    if not doc:
        return False
    session.delete(doc)
    session.commit()
    return True


def upcoming_expirations(session: Session, days: int = 30) -> list[Document]:
    """Documents dont la date d'expiration est passée ou dans les N prochains jours."""
    limit = dt.date.today() + dt.timedelta(days=days)
    stmt = (
        select(Document)
        .where(Document.date_expiration.is_not(None))
        .where(Document.date_expiration <= limit)
        .order_by(Document.date_expiration.asc())
    )
    return list(session.exec(stmt).all())
