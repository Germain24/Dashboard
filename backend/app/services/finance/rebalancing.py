"""
Service de rebalancing — compare les positions réelles à l'allocation cible du
dernier run Buffett terminé. Produit un diff acheter/vendre. Aucune exécution
de trade (règle absolue PLAN).

Révision CONV 4 :
- La **cible** de chaque ligne provient des budgets brokers configurés
  (BUDGET_BROKERS) via l'optimiseur — plus de bug "comme si le portefeuille
  valait 100 €".
- Les brokers en **actions entières** (tout sauf Trading212) affichent une cible
  et un delta en **nombre d'actions** ; Trading212 (pies) en % / €.
- On affiche **les deux références** : cible (budget à déployer) ET comparaison
  à la valeur actuelle du portefeuille.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yfinance as yf
from sqlmodel import Session, select

from app.models.finance import Position, BuffettRun, BuffettRunResult
from app.services.finance.buffett.config import Config


@dataclass
class RebalancingLine:
    ticker: str
    nom: str
    broker: str
    # Détenu (réel)
    quantite_actuelle: float
    valeur_actuelle_eur: float
    allocation_actuelle_pct: float      # % de la valeur actuelle du portefeuille
    # Cible (budget à déployer)
    cible_type: str                     # "pie" | "shares"
    cible_shares: Optional[int]         # actions entières (None si pie)
    prix_unitaire: float
    valeur_cible_eur: float
    allocation_cible_pct: float         # % du capital total (budgets brokers)
    # Diff
    delta_eur: float                    # >0 acheter, <0 vendre
    delta_shares: Optional[int]         # actions à acheter(+)/vendre(-) si broker entier
    action: str                         # "ACHETER" | "VENDRE" | "CONSERVER"
    ecart_pct: float = 0.0              # poids actuel - poids cible (points de %)
    alerte: bool = False                # |ecart| > seuil de rééquilibrage


@dataclass
class RebalancingDiff:
    run_id: int
    run_date: str
    valeur_totale_eur: float            # valeur actuelle réelle du portefeuille
    budget_total_eur: float             # capital total à déployer (budgets brokers)
    lignes: list[RebalancingLine] = field(default_factory=list)
    n_acheter: int = 0
    n_vendre: int = 0
    n_conserver: int = 0
    seuil_alerte_pct: float = 0.0
    n_alertes: int = 0


# Seuil (en points de %) au-delà duquel un écart poids actuel/cible déclenche une
# alerte. Pilotable par .env (FINANCE_REBALANCE_ALERT_PCT).
from app.core.config import settings as _settings
REBALANCE_ALERT_THRESHOLD_PCT = _settings.finance_rebalance_alert_pct


def _ecart_alerte(actuel_pct: float, cible_pct: float, seuil: float) -> tuple[float, bool]:
    ecart = round(actuel_pct - cible_pct, 2)
    return ecart, abs(ecart) > seuil


def _get_last_run(session: Session) -> Optional[BuffettRun]:
    stmt = (
        select(BuffettRun)
        .where(BuffettRun.statut == "termine")
        .order_by(BuffettRun.run_date.desc())  # type: ignore[attr-defined]
    )
    return session.exec(stmt).first()


def _get_run_results(session: Session, run_id: int) -> list[BuffettRunResult]:
    stmt = (
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .where(BuffettRunResult.allocation_pct.isnot(None))  # type: ignore[attr-defined]
        .order_by(BuffettRunResult.allocation_pct.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def _norm_broker(name) -> str:
    return "".join(filter(str.isalnum, str(name or "").upper()))


def _fetch_prices(tickers: list[str]) -> dict[str, float]:
    """Prix courants pour une liste de tickers. {ticker: prix}."""
    prices: dict[str, float] = {}
    tickers = [t for t in tickers if t]
    if not tickers:
        return prices
    try:
        data = yf.download(tickers, period="5d", auto_adjust=True, progress=False)
        close = data["Close"] if "Close" in getattr(data, "columns", []) else data
        for t in tickers:
            try:
                if t in close.columns:
                    s = close[t].dropna()
                    if len(s):
                        prices[t] = float(s.iloc[-1])
                elif len(tickers) == 1:
                    s = close.dropna()
                    if len(s):
                        prices[t] = float(s.iloc[-1])
            except Exception:
                pass
    except Exception:
        pass
    return prices


def _target_allocations(r: BuffettRunResult, budget_total: float) -> list[dict]:
    """Allocations cibles par broker pour un ticker.

    Source primaire : ``secteurs_extra['allocations']`` (détail actions/€/prix/type
    posé par l'optimiseur). Repli : reconstruire depuis allocation_pct (pie).
    """
    extra = (r.secteurs_extra or {}).get("allocations")
    if extra:
        return extra
    # Repli (anciens runs sans détail) : on traite comme une pie au % stocké
    eur = (r.allocation_pct or 0) / 100 * budget_total
    return [{
        "broker": r.broker_cible or "—",
        "shares": None,
        "eur": round(eur, 2),
        "prix": float(r.prix or 0),
        "type": "pie",
        "pct": r.allocation_pct or 0,
    }]


def _action(delta_eur: float) -> str:
    if abs(delta_eur) < 1:
        return "CONSERVER"
    return "ACHETER" if delta_eur > 0 else "VENDRE"


def compute_rebalancing_diff(session: Session) -> Optional[RebalancingDiff]:
    run = _get_last_run(session)
    if run is None:
        return None

    run_results = _get_run_results(session, run.id)
    positions = list(session.exec(select(Position)).all())
    budget_total = float(sum(Config.BUDGET_BROKERS.values())) or 0.0

    all_tickers = {r.ticker for r in run_results} | {p.ticker for p in positions}
    prices = _fetch_prices(list(all_tickers))

    # Valeur actuelle par (ticker, broker normalisé)
    pos_map: dict[tuple[str, str], tuple[Position, float]] = {}
    for p in positions:
        price = prices.get(p.ticker) or (p.pmu or 0.0)
        pos_map[(p.ticker, _norm_broker(p.broker))] = (p, price)

    valeur_totale = sum(price * (p.quantite or 0) for p, price in pos_map.values())
    if valeur_totale <= 0:
        from app.models.finance import SnapshotPortefeuille
        snap = session.exec(
            select(SnapshotPortefeuille).order_by(SnapshotPortefeuille.date.desc())
        ).first()
        valeur_totale = snap.valeur if snap and snap.valeur and snap.valeur > 0 else 0.0
    denom_actuel = valeur_totale if valeur_totale > 0 else 1.0

    lignes: list[RebalancingLine] = []
    seen: set[tuple[str, str]] = set()

    for r in run_results:
        for a in _target_allocations(r, budget_total):
            broker = a.get("broker") or (r.broker_cible or "—")
            key = (r.ticker, _norm_broker(broker))
            seen.add(key)
            cible_type = a.get("type") or "pie"
            cible_shares = a.get("shares")
            cible_eur = float(a.get("eur") or 0)
            prix = float(a.get("prix") or prices.get(r.ticker) or 0)

            pos, price = pos_map.get(key, (None, prices.get(r.ticker) or prix or 0))
            qte = float(pos.quantite) if pos else 0.0
            val_act = (price or prix) * qte
            delta_eur = cible_eur - val_act
            delta_shares = (int(cible_shares) - round(qte)) if cible_shares is not None else None

            alloc_actuelle = round(val_act / denom_actuel * 100, 2)
            alloc_cible = round(cible_eur / budget_total * 100, 2) if budget_total else 0.0
            ecart, alerte = _ecart_alerte(alloc_actuelle, alloc_cible, REBALANCE_ALERT_THRESHOLD_PCT)
            lignes.append(RebalancingLine(
                ticker=r.ticker,
                nom=r.nom or r.ticker,
                broker=broker,
                quantite_actuelle=round(qte, 4),
                valeur_actuelle_eur=round(val_act, 2),
                allocation_actuelle_pct=alloc_actuelle,
                cible_type=cible_type,
                cible_shares=int(cible_shares) if cible_shares is not None else None,
                prix_unitaire=round(prix, 4),
                valeur_cible_eur=round(cible_eur, 2),
                allocation_cible_pct=alloc_cible,
                delta_eur=round(delta_eur, 2),
                delta_shares=delta_shares,
                action=_action(delta_eur),
                ecart_pct=ecart,
                alerte=alerte,
            ))

    # Positions détenues hors cible -> à vendre
    for (ticker, brk), (pos, price) in pos_map.items():
        if (ticker, brk) in seen:
            continue
        val_act = price * (pos.quantite or 0)
        if val_act <= 0:
            continue
        alloc_actuelle = round(val_act / denom_actuel * 100, 2)
        ecart, alerte = _ecart_alerte(alloc_actuelle, 0.0, REBALANCE_ALERT_THRESHOLD_PCT)
        lignes.append(RebalancingLine(
            ticker=ticker,
            nom=ticker,
            broker=pos.broker or "—",
            quantite_actuelle=round(float(pos.quantite or 0), 4),
            valeur_actuelle_eur=round(val_act, 2),
            allocation_actuelle_pct=alloc_actuelle,
            cible_type="shares",
            cible_shares=0,
            prix_unitaire=round(price, 4),
            valeur_cible_eur=0.0,
            allocation_cible_pct=0.0,
            delta_eur=round(-val_act, 2),
            delta_shares=-round(float(pos.quantite or 0)),
            action="VENDRE",
            ecart_pct=ecart,
            alerte=alerte,
        ))

    lignes.sort(key=lambda l: abs(l.delta_eur), reverse=True)

    return RebalancingDiff(
        run_id=run.id,
        run_date=str(run.run_date),
        valeur_totale_eur=round(valeur_totale, 2),
        budget_total_eur=round(budget_total, 2),
        lignes=lignes,
        n_acheter=sum(1 for l in lignes if l.action == "ACHETER"),
        n_vendre=sum(1 for l in lignes if l.action == "VENDRE"),
        n_conserver=sum(1 for l in lignes if l.action == "CONSERVER"),
        seuil_alerte_pct=REBALANCE_ALERT_THRESHOLD_PCT,
        n_alertes=sum(1 for l in lignes if l.alerte),
    )
