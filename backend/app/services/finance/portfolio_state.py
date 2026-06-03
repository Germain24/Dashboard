"""État du portefeuille dérivé des transactions (source de vérité unique).

Fonction pure : à partir du ledger de transactions, des cours et des paramètres de
taxe, calcule positions (ACB), cash par broker, plus-value latente et réalisée,
dividendes, allocation (cash inclus) et taxes estimées. Sans DB ni réseau.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.cache import TTLCache

# Cache de l'état dérivé, invalidé explicitement à chaque écriture de transaction.
_state_cache = TTLCache(ttl_seconds=300.0)

# Paramètres de taxe par défaut (remplacés par FinanceSettings en phase 3).
DEFAULT_TAXE = {"taux_plus_value_pct": 25.0, "taux_dividende_pct": 15.0}


def invalidate_state() -> None:
    """À appeler après toute création/modif/suppression de transaction."""
    _state_cache.clear()


def get_tax_params(session) -> dict:
    """Paramètres de taxe courants (FinanceSettings si présent, sinon défauts)."""
    try:
        from app.models.finance import FinanceSettings  # type: ignore
        from sqlmodel import select
        s = session.exec(select(FinanceSettings)).first()
        if s:
            return {
                "taux_plus_value_pct": s.taux_plus_value_pct,
                "taux_dividende_pct": s.taux_dividende_pct,
            }
    except Exception:
        pass
    return dict(DEFAULT_TAXE)


def get_or_create_settings(session):
    """Retourne la ligne FinanceSettings (créée avec les défauts si absente)."""
    from app.models.finance import FinanceSettings
    from sqlmodel import select
    s = session.exec(select(FinanceSettings)).first()
    if not s:
        s = FinanceSettings()
        session.add(s)
        session.commit()
        session.refresh(s)
    return s


def get_portfolio_state(session) -> dict:
    """État dérivé complet (caché ; invalidé à l'écriture)."""
    cached = _state_cache.get("state")
    if cached is not None:
        return cached

    from sqlmodel import select
    from app.models.finance import Transaction
    from app.services.finance.prices import get_prices

    txs = list(session.exec(select(Transaction)).all())
    tickers = {
        (t.ticker or "").upper()
        for t in txs
        if t.type in ("achat", "vente", "dividende") and t.ticker and t.ticker.upper() != "CASH"
    }
    prix = get_prices(list(tickers)) if tickers else {}
    state = compute_portfolio_state(txs, prix, get_tax_params(session))
    _state_cache.set("state", state)
    return state


def _montant(t) -> float:
    """Montant cash d'une ligne (cash : quantite=1, prix=montant ; sinon q*pu)."""
    q = getattr(t, "quantite", 0) or 0
    pu = getattr(t, "prix_unitaire", 0) or 0
    return (q * pu) if q else pu


def compute_portfolio_state(transactions, prix: dict[str, float], taxe: dict) -> dict:
    """Dérive l'état complet du portefeuille depuis les transactions.

    transactions : itérable d'objets avec attributs
        type (achat|vente|dividende|depot|retrait|frais), ticker, broker,
        quantite, prix_unitaire, frais, date.
    prix : {ticker: cours_actuel}.
    taxe : {taux_plus_value_pct, taux_dividende_pct}.
    """
    txs = sorted(transactions, key=lambda t: (getattr(t, "date", None) or 0, getattr(t, "id", 0) or 0))

    book: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"qte": 0.0, "cout": 0.0})
    cash: dict[str, float] = defaultdict(float)
    realise = 0.0
    dividendes = 0.0
    depots = 0.0
    retraits = 0.0

    for t in txs:
        typ = str(getattr(t, "type", "") or "").lower()
        broker = getattr(t, "broker", None) or "default"
        ticker = (getattr(t, "ticker", "") or "").upper()
        q = float(getattr(t, "quantite", 0) or 0)
        pu = float(getattr(t, "prix_unitaire", 0) or 0)
        frais = float(getattr(t, "frais", 0) or 0)

        if typ == "achat":
            b = book[(ticker, broker)]
            b["qte"] += q
            b["cout"] += q * pu + frais
            cash[broker] -= q * pu + frais
        elif typ == "vente":
            b = book[(ticker, broker)]
            acb = b["cout"] / b["qte"] if b["qte"] > 0 else 0.0
            realise += (pu - acb) * q
            b["cout"] -= acb * q
            b["qte"] -= q
            if b["qte"] < 1e-9:
                b["qte"] = 0.0
                b["cout"] = 0.0
            cash[broker] += q * pu - frais
        elif typ == "dividende":
            m = _montant(t)
            cash[broker] += m
            dividendes += m
        elif typ == "depot":
            m = _montant(t)
            cash[broker] += m
            depots += m
        elif typ == "retrait":
            m = _montant(t)
            cash[broker] -= m
            retraits += m
        elif typ == "frais":
            cash[broker] -= _montant(t)

    # Positions courantes valorisées
    positions = []
    pl_latent_total = 0.0
    for (ticker, broker), b in book.items():
        if b["qte"] <= 1e-9:
            continue
        acb = b["cout"] / b["qte"] if b["qte"] > 0 else 0.0
        p = float(prix.get(ticker, 0) or 0)
        valeur = p * b["qte"]
        pl_latent = (p - acb) * b["qte"]
        pl_latent_total += pl_latent
        positions.append({
            "ticker": ticker,
            "broker": broker,
            "quantite": round(b["qte"], 6),
            "acb": round(acb, 2),
            "prix": round(p, 2),
            "valeur": round(valeur, 2),
            "pl_latent": round(pl_latent, 2),
            "pl_pct": round((p / acb - 1) * 100, 2) if acb > 0 else 0.0,
        })

    cash_total = round(sum(cash.values()), 2)
    valeur_positions = sum(pos["valeur"] for pos in positions)
    valeur_totale = round(valeur_positions + cash_total, 2)

    # Allocation (cash inclus)
    denom = valeur_totale if valeur_totale != 0 else 1.0
    allocation = [
        {"label": pos["ticker"], "valeur": pos["valeur"], "poids_pct": round(pos["valeur"] / denom * 100, 2)}
        for pos in sorted(positions, key=lambda x: x["valeur"], reverse=True)
    ]
    if cash_total != 0:
        allocation.append({"label": "Cash", "valeur": cash_total,
                           "poids_pct": round(cash_total / denom * 100, 2)})

    # Poids dans chaque position (sur valeur_totale)
    for pos in positions:
        pos["poids_pct"] = round(pos["valeur"] / denom * 100, 2)

    taux_pv = float(taxe.get("taux_plus_value_pct", 0) or 0)
    taux_div = float(taxe.get("taux_dividende_pct", 0) or 0)
    base_pv = max(0.0, realise)
    impot_pv = round(base_pv * taux_pv / 100, 2)
    impot_div = round(dividendes * taux_div / 100, 2)

    return {
        "positions": positions,
        "cash_par_broker": {k: round(v, 2) for k, v in cash.items()},
        "cash_total": cash_total,
        "investi_net": round(depots - retraits, 2),
        "valeur_totale": valeur_totale,
        "pl_realise": round(realise, 2),
        "pl_latent_total": round(pl_latent_total, 2),
        "dividendes_total": round(dividendes, 2),
        "allocation": allocation,
        "taxes": {
            "base_pv": round(base_pv, 2),
            "impot_pv": impot_pv,
            "base_div": round(dividendes, 2),
            "impot_div": impot_div,
            "total": round(impot_pv + impot_div, 2),
            "taux_plus_value_pct": taux_pv,
            "taux_dividende_pct": taux_div,
        },
    }
