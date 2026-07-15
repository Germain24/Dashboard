"""Modèles Voyage — planificateur d'itinéraire (liste de lieux à visiter).

Tables :
  - `lieu_voyage` : cache de la wishlist (master = data/imports/Voyage.xlsx)
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel


class LieuVoyage(SQLModel, table=True):
    """Cache d'un lieu de la wishlist voyage.

    Écrasé à chaque POST /voyage/sync, sauf `visite` qui est aussi écrit
    directement dans l'Excel par POST /voyage/confirmer (import_excel.py) —
    la synchro Excel->DB est un import destructif, donc l'Excel doit rester
    la source de vérité pour ce champ.
    """

    __tablename__ = "lieu_voyage"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    ville: Optional[str] = None
    pays: Optional[str] = None
    visite: bool = False
    aeroport_iata: Optional[str] = None
    jours_min: Optional[int] = None
    jours_max: Optional[int] = None
    cout_jour_estime: Optional[float] = None
