"""Calcul valeur portefeuille, positions, performance."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.core.timeutil import utcnow
from app.models.finance import Position, Transaction
from app.services.finance.metrics import (
    MAX_RELIABLE_DAILY_RETURN,
    adjusted_wealth_index,
    annualized_capital_return,
    money_weighted_annual_return,
    prepare_metric_snapshots,
    return_observations,
)


def get_positions(session: Session) -> list[dict]:
    """Retourne les positions enrichies (prix courant + P&L latent).

    Les positions du ledger sont fusionnées avec la table Position manuelle.
    Le ledger prime sur un doublon du même ticker chez le même broker, sans
    masquer les autres comptes maintenus manuellement.
    Les cours passent par le cache quotidien (un seul appel groupé par jour).
    """
    from app.models.finance import Transaction
    has_tx = session.exec(select(Transaction).limit(1)).first() is not None
    if has_tx:
        from app.services.finance.portfolio_state import get_portfolio_state
        st = get_portfolio_state(session)
        return [
            {
                "ticker": p["ticker"],
                "broker": p["broker"],
                "quantite": p["quantite"],
                "pmu": p["acb"],
                "devise": "EUR",
                "prix_actuel": p["prix"],
                "valeur_actuelle": p["valeur"],
                "pl_latent": p["pl_latent"],
                "pl_pct": p["pl_pct"],
            }
            for p in st["positions"]
        ]

    positions = list(session.exec(select(Position)).all())
    if not positions:
        return []
    from app.services.finance.prices import get_prices
    cours = get_prices([pos.ticker for pos in positions])
    result = []
    for pos in positions:
        prix_actuel = float(cours.get(pos.ticker, 0) or 0)
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


def get_title_detail(session: Session, ticker: str) -> dict:
    """Détail consolidé d'un titre : cours, P/E, score Buffett, poids, performance.

    Agrège les positions (tous brokers) + le dernier résultat Buffett du ticker.
    Fonctionne même si le titre n'est pas détenu (vue analyse).
    """
    ticker = ticker.upper().strip()
    all_positions = get_positions(session)
    matching = [p for p in all_positions if p["ticker"].upper() == ticker]

    qte = sum(p["quantite"] for p in matching)
    cost = sum((p["pmu"] or 0) * p["quantite"] for p in matching)
    pmu = cost / qte if qte > 0 else 0.0
    valeur = sum(p["valeur_actuelle"] for p in matching)

    if matching:
        prix = matching[0]["prix_actuel"]
    else:
        # Vue analyse : titre pas detenu, on veut quand meme le prix courant.
        from app.services.finance.prices import get_prices
        prix = float(get_prices([ticker]).get(ticker, 0) or 0)

    pl_pct = ((prix / pmu) - 1) * 100 if pmu > 0 else 0.0
    total = sum(p["valeur_actuelle"] for p in all_positions)
    poids_pct = (valeur / total * 100) if total > 0 else 0.0

    from app.services.finance.buffett.reporting import get_latest_result_for_ticker

    br = get_latest_result_for_ticker(session, ticker)

    return {
        "ticker": ticker,
        "nom": br.nom if br else None,
        "secteur": br.secteur if br else None,
        "pays": br.pays if br else None,
        "prix": round(prix, 2),
        "per": round(br.per, 2) if br and br.per else None,
        "score_buffett": round(br.chance_moat, 2) if br and br.chance_moat is not None else None,
        "quantite": qte,
        "pmu": round(pmu, 2),
        "valeur": round(valeur, 2),
        "poids_pct": round(poids_pct, 2),
        "pl_pct": round(pl_pct, 2),
        "detenu": qte > 0,
    }


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
            updated_at=utcnow(),
        )
        session.add(pos)
        new_positions.append(pos)
    session.commit()
    return new_positions


def time_weighted_return(snaps: list[tuple]) -> dict:
    """Rendement pondéré dans le temps (TWR) à partir des snapshots.

    ``snaps`` : liste de tuples ``(date, valeur, investit)`` triés par date.
    Le TWR retire l'effet des apports/retraits : pour chaque sous-période, le
    facteur de rendement est ``(valeur_i - apport_i) / valeur_{i-1}`` où
    ``apport_i = investit_i - investit_{i-1}``. On chaîne les facteurs puis on
    annualise sur la durée totale. Les deux rendements sont ``None`` si une
    rupture rend la chronologie des flux non défendable.
    """
    prepared = prepare_metric_snapshots(snaps)
    if len(prepared) < 2:
        return {"twr_pct": None, "twr_annualise_pct": None, "n_jours": 0}

    observations = return_observations(prepared, prepared=True)
    n_jours = (prepared[-1].date - prepared[0].date).days
    reliable = bool(observations) and all(
        observation.valid
        and abs(observation.daily_return) <= MAX_RELIABLE_DAILY_RETURN
        for observation in observations
    )
    if not reliable or n_jours <= 0:
        return {"twr_pct": None, "twr_annualise_pct": None, "n_jours": n_jours}

    factor = 1.0
    for observation in observations:
        factor *= observation.factor
    twr_pct = (factor - 1.0) * 100.0
    twr_annualise = (factor ** (365.25 / n_jours) - 1.0) * 100.0
    return {
        "twr_pct": round(twr_pct, 2),
        "twr_annualise_pct": round(twr_annualise, 2),
        "n_jours": n_jours,
    }


def get_perf_metrics(session: Session) -> dict:
    """Métriques de performance depuis l'historique des snapshots."""
    # ``get_history`` réconcilie notamment le capital investi depuis les flux
    # documentés. La carte de performance doit consommer la même série que le
    # graphique et les métriques de risque, pas les lignes brutes divergentes.
    from app.services.finance.snapshots import get_history

    snaps = get_history(session, limit=10_000)
    if not snaps:
        return {}
    latest = snaps[-1]
    valeur = latest.valeur
    investit = latest.investit
    pl_total = valeur - investit
    pl_pct = (pl_total / investit * 100) if investit else 0.0

    prepared = prepare_metric_snapshots(snaps)
    observations = return_observations(prepared, prepared=True)

    # Drawdown de l'indice de performance, pas de la valeur brute : un apport,
    # un retrait ou un sous-compte momentanément absent n'est pas une perte.
    wealth = adjusted_wealth_index(observations)
    peak = wealth[0]
    mdd = 0.0
    for point in wealth:
        peak = max(peak, point)
        if peak > 0:
            mdd = max(mdd, (peak - point) / peak * 100.0)

    # YTD
    today = dt.date.today()
    debut_annee = dt.date(today.year, 1, 1)
    snap_debut = next((s for s in snaps if s.date >= debut_annee), snaps[0])
    ytd = ((valeur / snap_debut.valeur) - 1) * 100 if snap_debut.valeur > 0 else 0.0

    # Rendement pondéré dans le temps (retire l'effet des apports)
    twr = time_weighted_return([(s.date, s.valeur, s.investit) for s in snaps])

    # CAGR demandé par l'interface : annualisation explicite du multiple
    # valeur/capital investi. Il reste séparé du TWR, qui est nullable lorsque
    # la chronologie des flux n'est pas suffisamment fiable.
    start_date = prepared[0].date if prepared else snaps[0].date
    cagr = annualized_capital_return(valeur, investit, start_date, latest.date)
    mwr = money_weighted_annual_return(prepared, prepared=True)

    return {
        "valeur": valeur,
        "investit": investit,
        "pl_total": pl_total,
        "pl_pct": round(pl_pct, 2),
        "max_drawdown_pct": round(mdd, 2),
        "ytd_pct": round(ytd, 2),
        "cagr_pct": cagr,
        "mwr_annualise_pct": mwr,
        "twr_pct": twr["twr_pct"],
        "twr_annualise_pct": twr["twr_annualise_pct"],
        "date_snapshot": latest.date.isoformat(),
    }
