"""Modèles Finance — watchlist Buffett, transactions, positions, snapshots."""

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class WatchlistEntry(SQLModel, table=True):
    """Action analysée (Buffett scoring + agrégation broker).

    Source : ToutBroker.xlsx — chaque ligne est une action avec son ticker
    Yahoo, ses indicateurs (PER, EPS, croissance, PEG…), son scoring MOAT
    et ses positions par broker.
    """

    __tablename__ = "watchlist_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(unique=True, index=True)
    nom: Optional[str] = None
    pays: Optional[str] = None
    secteur: Optional[str] = None

    # Indicateurs
    prix: Optional[float] = None
    eps: Optional[float] = None
    per: Optional[float] = None
    croissance: Optional[float] = None
    peg: Optional[float] = None
    volume: Optional[float] = None
    chance_moat: Optional[float] = None  # score Buffett 0-100
    poids: Optional[float] = None

    # Statut achat
    achat: bool = False

    # Positions par broker (peuvent évoluer)
    trading_212: Optional[float] = None
    bourse_direct: Optional[float] = None
    bourse_direct_2: Optional[float] = None
    ibkr: Optional[float] = None

    # Secteurs supplémentaires éventuels
    secteurs_extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class SnapshotPortefeuille(SQLModel, table=True):
    """Valeur totale du portefeuille à une date donnée.

    Source : Historique_portefeuille.xlsx (Date, Valeur, Investit).
    """

    __tablename__ = "snapshot_portefeuille"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(unique=True, index=True)
    valeur: float
    investit: float


class Transaction(SQLModel, table=True):
    """Transactions individuelles (achat / vente / dividende).

    Tables vide en CONV 1, remplie en CONV 4.
    """

    __tablename__ = "transaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.datetime = Field(index=True)
    ticker: str = Field(index=True)
    broker: Optional[str] = None
    type: str  # "achat" | "vente" | "dividende" | "frais"
    quantite: float
    prix_unitaire: float
    devise: str = "EUR"
    frais: float = 0.0
    note: Optional[str] = None


class Position(SQLModel, table=True):
    """Position courante d'une action chez un broker.

    Calculée à partir des transactions, snapshotée pour rapidité.
    """

    __tablename__ = "position"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True)
    broker: str = Field(index=True)
    quantite: float
    pmu: Optional[float] = None  # prix moyen unitaire
    devise: str = "EUR"
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
