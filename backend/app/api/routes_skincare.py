import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.models.skincare import SkincareLog
from app.services.skincare import products as svc

router = APIRouter(prefix="", tags=["skincare"])


class ProductCreate(BaseModel):
    nom: str
    type: str = "autre"
    moment: str = "AM"
    ordre: int = 0
    frequence_type: str = "quotidien"
    frequence_jours: str | None = None
    frequence_n: int | None = None
    apres_douche: bool = False
    soir_seulement: bool = False
    pas_avant_soleil: bool = False
    duree_min: int = 2
    stock_qte: float | None = None
    unite: str | None = None
    date_ouverture: dt.date | None = None
    date_peremption: dt.date | None = None
    cout: float = 0.0


class LogCreate(BaseModel):
    date_jour: dt.date
    moment: str
    produits_ids: str = ""
    note: str | None = None


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
def update_product(product_id: int, body: dict, session: Session = Depends(get_session)):
    p = svc.update_product(session, product_id, body)
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
    session.commit()
    session.refresh(log)
    return log
