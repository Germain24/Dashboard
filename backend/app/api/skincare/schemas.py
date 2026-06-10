"""Schémas du module Skincare (extraits de routes_skincare.py, #512)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


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


class ProductUpdate(BaseModel):
    nom: str | None = None
    type: str | None = None
    moment: str | None = None
    ordre: int | None = None
    frequence_type: str | None = None
    frequence_jours: str | None = None
    frequence_n: int | None = None
    apres_douche: bool | None = None
    soir_seulement: bool | None = None
    pas_avant_soleil: bool | None = None
    duree_min: int | None = None
    stock_qte: float | None = None
    unite: str | None = None
    date_ouverture: dt.date | None = None
    date_peremption: dt.date | None = None
    cout: float | None = None
    actif: bool | None = None


class LogCreate(BaseModel):
    date_jour: dt.date
    moment: str
    produits_ids: str = ""
    note: str | None = None
