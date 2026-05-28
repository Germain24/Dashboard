"""Calcul valeur portefeuille, positions, performance."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.finance import Position, SnapshotPortefeuille, Transaction


def get_positions(session: Session) -> list[dict]:
    """Retourne les positions enrichies (prix courant + P&L latent via yfinance)."""
    positions = list(session.exec(select(Position)).all())
    if not positions:
        return []
    result = []
    for pos in positions:
        prix_actuel = 0.0
        try:
            import yfinance as yf
            info = yf.Ticker(pos.ticker).fast_info
            prix_actuel = float(info.get("last_price", 0) or 0)
        except Exception:
            pass
        valeur_actuelle = prix_actuel * pos.quantite
        pmu = pos.pmu or 0.0
        pl_latent = (prix_actuel - pmu) * pos.quantite if pmu else 0.0
        pl_pct = ((prix_actuel / pmu) - 1) * 100 if pmu and pmu > 0 else 0.0
        result.append({
            "ticker": pos.ticker,
            "broker": pos.broker,
            "quantite": pos.quantite,
            "pmu": pmu,
            "devise": pos.devise,
            "prix_actuel": prix_actuel,
            "valeur_actuelle": valeur_actuelle,
            "pl_latent": pl_latent,
            "pl_pct": pl_pct,
        })
    return result


def rebuild_positions_from_transactions(session: Session) -> list[Position]:
    """Reconstruit les positions depuis les transactions (FIFO simple)."""
    txs = list(session.exec(
        select(Transaction).order_by(Transaction.date.asc())
    ).all())
    # (ticker, broker) → {quantite, pmu}
    book: dict[tuple[str, str], dict] = {}
    for tx in txs:
        key = (tx.ticker, tx.broker or "default")
        if key not in book:
            book[key] = {"quantite": 0.0, "cost": 0.0}
        if tx.type == "achat":
            old_q = book[key]["quantite"]
            new_q = old_q + tx.quantite
            book[key]["cost"] += tx.quantite * tx.prix_unitaire + tx.frais
            book[key]["quantite"] = new_q
        elif tx.type == "vente":
            book[key]["quantite"] = max(0.0, book[key]["quantite"] - tx.quantite)
        elif tx.type == "dividende":
            pass  # dividendes pas comptabilisés dans le coût de revient

    # Supprimer l'existant + recréer (note 16 : pas de cascade FK)
    existing = list(session.exec(select(Position)).all())
    for e in existing:
        session.delete(e)
    session.flush()

    new_positions = []
    for (ticker, broker), vals in book.items():
        if vals["quantite"] <= 0:
            continue
        pmu = vals["cost"] / vals["quantite"] if vals["quantite"] > 0 else 0
        pos = Position(
            ticker=ticker,
            broker=broker,
            quantite=vals["quantite"],
            pmu=pmu,
            updated_at=dt.datetime.utcnow(),
        )
        session.add(pos)
        new_positions.append(pos)
    session.commit()
    return new_positions


def get_perf_metrics(session: Session) -> dict:
    """Métriques de performance depuis l'historique des snapshots."""
    snaps = list(session.exec(
        select(SnapshotPortefeuille).order_by(SnapshotPortefeuille.date.asc())
    ).all())
    if not snaps:
        return {}
    latest = snaps[-1]
    valeur = latest.valeur
    investit = latest.investit
    pl_total = valeur - investit
    pl_pct = (pl_total / investit * 100) if investit else 0.0

    # Max drawdown depuis le plus haut
    peak = max(s.valeur for s in snaps)
    mdd = ((valeur - peak) / peak * 100) if peak > 0 else 0.0

    # YTD
    today = dt.date.today()
    debut_annee = dt.date(today.year, 1, 1)
    snap_debut = next((s for s in snaps if s.date >= debut_annee), snaps[0])
    ytd = ((valeur / snap_debut.valeur) - 1) * 100 if snap_debut.valeur > 0 else 0.0

    return {
        "valeur": valeur,
        "investit": investit,
        "pl_total": pl_total,
        "pl_pct": round(pl_pct, 2),
        "max_drawdown_pct": round(mdd, 2),
        "ytd_pct": round(ytd, 2),
        "date_snapshot": latest.date.isoformat(),
    }
