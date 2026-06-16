"""Modèle PatrimoineItem (#RealT/emprunt) — actifs manuels & passifs.

Pour les avoirs hors portefeuille actions (RealT/immobilier tokenisé, crypto…)
et les dettes (emprunt étudiant), saisis et valorisés à la main. Sert à une vue
patrimoine net = portefeuille + actifs − passifs.
"""

from __future__ import annotations

import datetime as dt

from app.core.timeutil import utcnow
from sqlmodel import SQLModel, Field


class PatrimoineItem(SQLModel, table=True):
    __tablename__ = "patrimoine_item"
    id: int | None = Field(default=None, primary_key=True)
    type: str = "actif"               # "actif" | "passif"
    label: str
    categorie: str = ""               # ex. "RealT", "crypto", "emprunt étudiant"
    valeur: float = 0.0               # actif : valeur ; passif : solde dû (positif)
    taux_pct: float | None = None     # passif : taux d'intérêt annuel
    mensualite: float | None = None   # passif : mensualité
    devise: str = "EUR"
    updated_at: dt.datetime = Field(default_factory=utcnow)
    created_at: dt.datetime = Field(default_factory=utcnow)
