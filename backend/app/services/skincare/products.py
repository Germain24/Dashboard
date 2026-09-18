"""Service produits skincare : CRUD, routine ordonnée, dû du jour, rachat."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.skincare import SkincareProduct
from app.services.skincare.frequency import is_due_on


def list_products(session: Session, *, actifs_only: bool = True) -> list[SkincareProduct]:
    q = select(SkincareProduct)
    if actifs_only:
        q = q.where(SkincareProduct.actif == True)  # noqa: E712
    q = q.order_by(SkincareProduct.moment, SkincareProduct.ordre)
    return list(session.exec(q).all())


def create_product(session: Session, data: dict) -> SkincareProduct:
    p = SkincareProduct(**data)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def update_product(session: Session, product_id: int, data: dict) -> SkincareProduct | None:
    p = session.get(SkincareProduct, product_id)
    if not p:
        return None
    for k, v in data.items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def delete_product(session: Session, product_id: int) -> bool:
    """Suppression logique (actif=False)."""
    p = session.get(SkincareProduct, product_id)
    if not p:
        return False
    p.actif = False
    session.add(p)
    session.commit()
    return True


def routine_for(session: Session, moment: str) -> list[SkincareProduct]:
    """Produits actifs d'un moment (AM/PM), dans l'ordre d'application.
    Inclut les produits 'les_deux'."""
    q = (
        select(SkincareProduct)
        .where(SkincareProduct.actif == True)  # noqa: E712
        .where(SkincareProduct.moment.in_([moment, "les_deux"]))  # type: ignore[attr-defined]
        .order_by(SkincareProduct.ordre)
    )
    return list(session.exec(q).all())


def due_on(session: Session, date: dt.date) -> list[SkincareProduct]:
    """Produits actifs dus à une date (hors n_par_semaine, géré par l'orchestrateur)."""
    return [p for p in list_products(session) if is_due_on(p, date)]


def to_repurchase(session: Session, today: dt.date | None = None) -> list[SkincareProduct]:
    """Produits à racheter : stock épuisé (<=0) ou périmés."""
    today = today or dt.date.today()
    out: list[SkincareProduct] = []
    for p in list_products(session):
        low = p.stock_qte is not None and p.stock_qte <= 0
        expired = p.date_peremption is not None and p.date_peremption < today
        if low or expired:
            out.append(p)
    return out


DEFAULT_PRODUCTS = [
    {"nom": "Nettoyant doux", "type": "nettoyant", "moment": "les_deux", "ordre": 0},
    {"nom": "Sérum vitamine C", "type": "serum", "moment": "AM", "ordre": 1},
    {"nom": "Hydratant", "type": "hydratant", "moment": "les_deux", "ordre": 2},
    {"nom": "SPF 50", "type": "spf", "moment": "AM", "ordre": 3, "pas_avant_soleil": False},
    {"nom": "Rétinoïde", "type": "retinoide", "moment": "PM", "ordre": 4, "soir_seulement": True,
     "frequence_type": "n_par_semaine", "frequence_n": 3},
    {"nom": "Exfoliant", "type": "exfoliant", "moment": "PM", "ordre": 5,
     "frequence_type": "n_par_semaine", "frequence_n": 2},
]


def seed_skincare(session: Session) -> None:
    """Insère des produits de démo si la table est vide (idempotent)."""
    existing = session.exec(select(SkincareProduct)).first()
    if existing:
        return
    for data in DEFAULT_PRODUCTS:
        session.add(SkincareProduct(**data))
    session.commit()
