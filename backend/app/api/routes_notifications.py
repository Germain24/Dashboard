from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.scheduler import Notification

router = APIRouter(prefix="", tags=["notifications"])

@router.get("")
def list_notifications(limit: int = 20, session: Session = Depends(get_session)):
    return session.exec(
        select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    ).all()

@router.patch("/{id}/read")
def mark_read(id: int, session: Session = Depends(get_session)):
    n = session.get(Notification, id)
    if n:
        n.lu = True
        session.add(n)
        session.commit()
    return {"ok": True}

@router.post("/read-all")
def mark_all_read(session: Session = Depends(get_session)):
    notifs = session.exec(select(Notification).where(Notification.lu == False)).all()
    for n in notifs:
        n.lu = True
        session.add(n)
    session.commit()
    return {"marked": len(notifs)}
