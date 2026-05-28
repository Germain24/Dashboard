"""Modèles Finance — CONV 4 : BuffettRun, BuffettRunResult, snapshots, positions, transactions."""

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class BuffettRun(SQLModel, table=True):
    """Une analyse mensuelle Buffett complète.

    Statuts : pending → running → completed | error
    """

    __tablename__ = "buffett_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_date: dt.date = Field(index=True)
    statut: str = Field(default="pending")  # pending | running | completed | error
    n_tickers_total: int = Field(default=0)
    n_tickers_analyzed: int = Field(default=0)
    progress_pct: float = Field(default=0.0)
    params_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    duree_sec: Optional[float] = None
    resume: Optional[str] = None
    erreur: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class BuffettRunResult(SQLModel, table=True):
    """Un ticker scoré dans le cadre d'un BuffettRun.

    Anciennement watchlist_entry (CONV 1). Renommé + FK run_id ajouté.
    Les 1741 lignes importées ont run_id=NULL (données historiques).
    """

    __tablename__ = "buffett_run_result"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: Optional[int] = Field(default=None, foreign_key="buffett_run.id", index=True)

    ticker: str = Field(unique=True, index=True)
    nom: Optional[str] = None
    pays: Optional[str] = None
    secteur: Optional[str] = None

    # Indicateurs financiers
    prix: Optional[float] = None
    eps: Optional[float] = None
    per: Optional[float] = None
    croissance: Optional[float] = None
    peg: Optional[float] = None
    volume: Optional[float] = None
    chance_moat: Optional[float] = None  # score 0-100
    poids: Optional[float] = None

    # Signal achat + allocation
    achat: bool = False
    allocation_pct: Optional[float] = None  # % portefeuille cible (dernier run)
    broker_cible: Optional[str] = None

    # Positions par broker (héritage CONV 1)
    trading_212: Optional[float] = None
    bourse_direct: Optional[float] = None
    bourse_direct_2: Optional[float] = None
    ibkr: Optional[float] = None

    secteurs_extra: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class SnapshotPortefeuille(SQLModel, table=True):
    """Valeur totale du portefeuille à une date donnée (1 ligne/jour)."""

    __tablename__ = "snapshot_portefeuille"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(unique=True, index=True)
    valeur: float
    investit: float


class Transaction(SQLModel, table=True):
    """Transaction individuelle : achat / vente / dividende / frais."""

    __tablename__ = "transaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.datetime = Field(index=True)
    ticker: str = Field(index=True)
    broker: Optional[str] = None
    type: str  # achat | vente | dividende | frais
    quantite: float
    prix_unitaire: float
    devise: str = "EUR"
    frais: float = 0.0
    note: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class Position(SQLModel, table=True):
    """Position courante d'une action chez un broker (reconstruite depuis les transactions)."""

    __tablename__ = "position"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True)
    broker: str = Field(index=True)
    quantite: float
    pmu: Optional[float] = None  # prix moyen unitaire
    devise: str = "EUR"
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
