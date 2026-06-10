from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.notifications.schemas import PrefUpdate
from app.core.db import get_session
from app.models.scheduler import Notification
from app.services.scheduler import notif_prefs

router = APIRouter(prefix="", tags=["notifications"])


@router.get("")
def list_notifications(limit: int = 20, session: Session = Depends(get_session)):
    """Notifications récentes, en masquant les sources désactivées (#171)."""
    rows = session.exec(
        select(Notification).order_by(Notification.created_at.desc())
    ).all()
    rows = notif_prefs.filter_enabled(rows)
    return rows[:limit]


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
    notifs = session.exec(select(Notification).where(Notification.lu == False)).all()  # noqa: E712
    for n in notifs:
        n.lu = True
        session.add(n)
    session.commit()
    return {"marked": len(notifs)}


@router.delete("/clear")
def clear_all(session: Session = Depends(get_session)):
    """Efface toutes les notifications (#169)."""
    rows = session.exec(select(Notification)).all()
    for n in rows:
        session.delete(n)
    session.commit()
    return {"deleted": len(rows)}


# ── Préférences par source (#171) ────────────────────────────────────────────

@router.get("/prefs")
def get_prefs(session: Session = Depends(get_session)):
    """Sources connues (distinctes des notifications) + leur état activé/désactivé."""
    sources = sorted({
        (n.source or "system")
        for n in session.exec(select(Notification)).all()
    })
    prefs = notif_prefs.get_prefs()
    # Inclure aussi les sources déjà réglées même sans notification existante.
    for s in prefs:
        if s not in sources:
            sources.append(s)
    return [{"source": s, "enabled": prefs.get(s, True)} for s in sorted(sources)]


@router.post("/prefs")
def set_pref(body: PrefUpdate):
    notif_prefs.set_source(body.source, body.enabled)
    return {"ok": True, "source": body.source, "enabled": body.enabled}
