import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.api.skincare.schemas import LogCreate, ProductCreate, ProductUpdate
from app.core.db import get_session
from app.models.skincare import SkincareLog
from app.services.skincare import products as svc

router = APIRouter(prefix="", tags=["skincare"])


@router.get("/ping")
def ping():
    return {"module": "skincare", "ready": True}


@router.get("/products")
def list_products(session: Session = Depends(get_session)):
    return svc.list_products(session)


@router.post("/products", status_code=201)
def create_product(body: ProductCreate, session: Session = Depends(get_session)):
    return svc.create_product(session, body.model_dump())


@router.patch("/products/{product_id}")
def update_product(product_id: int, body: ProductUpdate, session: Session = Depends(get_session)):
    p = svc.update_product(session, product_id, body.model_dump(exclude_unset=True))
    if not p:
        raise HTTPException(404, f"Produit {product_id} introuvable")
    return p


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, session: Session = Depends(get_session)):
    if not svc.delete_product(session, product_id):
        raise HTTPException(404, f"Produit {product_id} introuvable")


@router.get("/routine")
def routine(moment: str, session: Session = Depends(get_session)):
    if moment not in ("AM", "PM"):
        raise HTTPException(422, "moment doit être AM ou PM")
    return svc.routine_for(session, moment)


@router.get("/today")
def today(session: Session = Depends(get_session)):
    today_d = dt.date.today()
    return {
        "date": str(today_d),
        "AM": svc.routine_for(session, "AM"),
        "PM": svc.routine_for(session, "PM"),
        "due": svc.due_on(session, today_d),
    }


@router.get("/to-repurchase")
def to_repurchase(session: Session = Depends(get_session)):
    return svc.to_repurchase(session)


@router.post("/log", status_code=201)
def create_log(body: LogCreate, session: Session = Depends(get_session)):
    log = SkincareLog(**body.model_dump())
    session.add(log)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Log {body.moment} du {body.date_jour} existe déjà")
    session.refresh(log)
    return log
