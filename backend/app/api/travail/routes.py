import datetime as dt
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.travail.schemas import STATUTS, ShiftCreate, ShiftUpdate, TauxHoraireUpdate
from app.core.db import get_session
from app.models.travail import WorkShift
from app.services.travail import settings as svc_settings
from app.services.travail import shifts as svc

router = APIRouter(prefix="", tags=["travail"])

_MOIS_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_HEURE_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_heures(*valeurs: str | None) -> None:
    for v in valeurs:
        if v is not None and not _HEURE_RE.match(v):
            raise HTTPException(422, f"Heure invalide : {v} (format HH:MM)")


@router.get("/ping")
def ping():
    return {"module": "travail", "ready": True}


@router.get("/shifts")
def list_shifts(mois: str | None = None, session: Session = Depends(get_session)):
    q = select(WorkShift)
    if mois:
        if not _MOIS_RE.match(mois):
            raise HTTPException(422, "mois doit être au format YYYY-MM")
        annee, m = (int(x) for x in mois.split("-"))
        debut = dt.date(annee, m, 1)
        fin = dt.date(annee + 1, 1, 1) if m == 12 else dt.date(annee, m + 1, 1)
        q = q.where(WorkShift.date_jour >= debut, WorkShift.date_jour < fin)
    shifts = session.exec(q.order_by(WorkShift.date_jour, WorkShift.heure_debut)).all()
    return [{**s.model_dump(), "heures": svc.duree_heures(s)} for s in shifts]


@router.post("/shifts", status_code=201)
def create_shift(body: ShiftCreate, session: Session = Depends(get_session)):
    if body.statut not in STATUTS:
        raise HTTPException(422, f"statut doit être parmi {STATUTS}")
    _check_heures(body.heure_debut, body.heure_fin)
    shift = WorkShift(**body.model_dump())
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return shift


@router.patch("/shifts/{shift_id}")
def update_shift(shift_id: int, body: ShiftUpdate, session: Session = Depends(get_session)):
    shift = session.get(WorkShift, shift_id)
    if not shift:
        raise HTTPException(404, f"Shift {shift_id} introuvable")
    data = body.model_dump(exclude_unset=True)
    if "statut" in data and data["statut"] not in STATUTS:
        raise HTTPException(422, f"statut doit être parmi {STATUTS}")
    _check_heures(data.get("heure_debut"), data.get("heure_fin"))
    for k, v in data.items():
        setattr(shift, k, v)
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return shift


@router.delete("/shifts/{shift_id}", status_code=204)
def delete_shift(shift_id: int, session: Session = Depends(get_session)):
    shift = session.get(WorkShift, shift_id)
    if not shift:
        raise HTTPException(404, f"Shift {shift_id} introuvable")
    session.delete(shift)
    session.commit()


@router.get("/summary")
def summary(mois: str, session: Session = Depends(get_session)):
    if not _MOIS_RE.match(mois):
        raise HTTPException(422, "mois doit être au format YYYY-MM")
    return svc.summary(session, mois)


@router.get("/settings")
def get_settings():
    return {"taux_horaire": svc_settings.get_taux_horaire()}


@router.put("/settings")
def put_settings(body: TauxHoraireUpdate):
    return {"taux_horaire": svc_settings.set_taux_horaire(body.taux_horaire)}
