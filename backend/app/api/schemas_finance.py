"""Pydantic v2 schemas for Finance API.

Field names match the actual model/service outputs to avoid mapping bugs.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---------------------------------------------------------------------------
# Snapshot / History  (model fields: valeur, investit)
# ---------------------------------------------------------------------------

class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.date
    valeur: float
    investit: float


class HistoryPointOut(BaseModel):
    date: dt.date
    valeur: float
    investit: float


# ---------------------------------------------------------------------------
# Portfolio / Positions  (from get_positions() dict)
# ---------------------------------------------------------------------------

class PositionOut(BaseModel):
    ticker: str
    broker: Optional[str] = None
    quantite: float
    pmu: Optional[float] = None
    devise: str = "EUR"
    prix_actuel: float = 0.0
    valeur_actuelle: float = 0.0
    pl_latent: float = 0.0
    pl_pct: float = 0.0


class PositionCreate(BaseModel):
    """Schema pour creer ou mettre a jour une position manuelle."""
    ticker: str
    quantite: float
    pmu: Optional[float] = None         # prix moyen unitaire
    devise: str = "EUR"
    broker: Optional[str] = None


class PositionIdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    broker: Optional[str] = None
    quantite: float
    pmu: Optional[float] = None
    devise: str = "EUR"
    updated_at: Optional[dt.datetime] = None


class PerfMetricsOut(BaseModel):
    valeur: float = 0.0
    investit: float = 0.0
    pl_total: float = 0.0
    pl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    ytd_pct: float = 0.0
    twr_pct: float = 0.0
    twr_annualise_pct: float = 0.0
    date_snapshot: Optional[str] = None


# ---------------------------------------------------------------------------
# Benchmarks  (from get_portfolio_vs_benchmarks())
# ---------------------------------------------------------------------------

class BenchmarkSeriePoint(BaseModel):
    date: str
    valeur: float


class BenchmarkOut(BaseModel):
    nom: str
    ticker: str
    perf_1a_pct: Optional[float] = None
    perf_6m_pct: Optional[float] = None
    perf_mtd_pct: Optional[float] = None
    serie: list[BenchmarkSeriePoint] = []


# ---------------------------------------------------------------------------
# Risk  (from get_risk_metrics())
# ---------------------------------------------------------------------------

class RiskMetricsOut(BaseModel):
    max_drawdown_pct: float = 0.0
    volatilite_annuelle_pct: float = 0.0
    sharpe: Optional[float] = None
    hhi: float = 0.0
    hhi_label: str = "—"
    n_positions: int = 0


class TreemapNodeOut(BaseModel):
    id: str
    parent: str
    valeur: float
    label: str


# ---------------------------------------------------------------------------
# Transactions  (model fields: type, date — not type_transaction)
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    ticker: str
    type_transaction: str = Field(..., pattern="^(?i:(achat|vente|dividende|frais|depot|retrait))$")
    date_transaction: dt.date
    quantite: float
    prix_unitaire: float
    frais: float = 0.0
    devise: str = "EUR"
    broker: Optional[str] = None
    note: Optional[str] = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.datetime
    ticker: str
    broker: Optional[str] = None
    type: str
    quantite: float
    prix_unitaire: float
    frais: float
    devise: str
    note: Optional[str] = None
    created_at: dt.datetime


class ImportResultOut(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


# ---------------------------------------------------------------------------
# Buffett runs  (model fields match)
# ---------------------------------------------------------------------------

class BuffettRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_date: dt.date
    statut: str
    n_tickers_total: int = 0
    n_tickers_analyzed: int = 0
    progress_pct: float = 0.0
    duree_sec: Optional[float] = None
    resume: Optional[str] = None
    erreur: Optional[str] = None
    created_at: dt.datetime


class BuffettResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: Optional[int] = None
    ticker: str
    nom: Optional[str] = None
    chance_moat: Optional[float] = None
    secteur: Optional[str] = None
    pays: Optional[str] = None
    allocation_pct: Optional[float] = None
    broker_cible: Optional[str] = None
    # Détail brut par broker (non sérialisé) ; exposé via `allocations`.
    secteurs_extra: Optional[dict] = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def score(self) -> Optional[float]:
        """Alias de `chance_moat` attendu par le front (colonne Score)."""
        return self.chance_moat

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allocations(self) -> Optional[list[dict]]:
        """Détail actionnable par broker : pie % (Trading212) ou nb d'actions.

        Chaque entrée : {broker, type 'pie'|'shares', pie_pct, shares, eur, prix, pct}.
        """
        if not self.secteurs_extra:
            return None
        allocs = self.secteurs_extra.get("allocations")
        return allocs or None


class BuffettRunDetailOut(BaseModel):
    run: BuffettRunOut
    top_results: list[BuffettResultOut]
    allocation_cible: list[BuffettResultOut]


class BuffettProgressOut(BaseModel):
    run_id: Optional[int] = None
    statut: str
    progress_pct: float
    n_done: Optional[int] = None
    n_total: Optional[int] = None
    active: bool = False  # True = une analyse tourne reellement dans ce process
    # Epoch (s) de reprise estimee si l'analyse est en pause (plafond API Yahoo
    # atteint) ; None sinon. Permet d'afficher "en pause, reprise ~HH:MM" (#193).
    paused_until: Optional[float] = None


# ---------------------------------------------------------------------------
# Rebalancing
# ---------------------------------------------------------------------------

class RebalancingLineOut(BaseModel):
    ticker: str
    nom: str
    broker: str = "—"
    quantite_actuelle: float = 0.0
    valeur_actuelle_eur: float
    allocation_actuelle_pct: float
    cible_type: str = "pie"               # "pie" | "shares"
    cible_shares: Optional[int] = None    # actions entières cibles (None si pie)
    prix_unitaire: float = 0.0
    valeur_cible_eur: float
    allocation_cible_pct: float
    delta_eur: float
    delta_shares: Optional[int] = None    # actions à acheter(+)/vendre(-)
    action: str
    ecart_pct: float = 0.0
    alerte: bool = False


class RebalancingDiffOut(BaseModel):
    run_id: int
    run_date: str
    valeur_totale_eur: float
    budget_total_eur: float = 0.0
    lignes: list[RebalancingLineOut]
    n_acheter: int
    n_vendre: int
    n_conserver: int
    seuil_alerte_pct: float = 0.0
    n_alertes: int = 0
