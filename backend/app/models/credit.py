"""Modèles Crédit — comptes, historique de pointage, profil (#marge-credit).

Sert le module "Marge de crédit" : feuille de route pour maximiser la marge
de crédit totale (toutes institutions) à une date cible, à partir de données
saisies manuellement (pas d'API de bureau de crédit accessible en pratique
pour un particulier).
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Field, SQLModel

from app.core.timeutil import utcnow


class CreditProfile(SQLModel, table=True):
    __tablename__ = "credit_profile"
    id: int | None = Field(default=None, primary_key=True)
    revenu_annuel: float = 0.0
    date_arrivee_canada: dt.date = Field(default_factory=lambda: dt.date.today())
    date_cible: dt.date = Field(default_factory=lambda: dt.date.today())
    nom: str | None = None
    updated_at: dt.datetime = Field(default_factory=utcnow)


class CreditAccount(SQLModel, table=True):
    __tablename__ = "credit_account"
    id: int | None = Field(default=None, primary_key=True)
    institution: str
    produit: str
    limite_actuelle: float = 0.0
    date_ouverture: dt.date
    derniere_augmentation: dt.date | None = None
    statut: str = "actif"  # "actif" | "ferme"
    notes: str | None = None
    updated_at: dt.datetime = Field(default_factory=utcnow)
    created_at: dt.datetime = Field(default_factory=utcnow)


class CreditScoreEntry(SQLModel, table=True):
    __tablename__ = "credit_score_entry"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    score: int
    source: str = ""
    created_at: dt.datetime = Field(default_factory=utcnow)
