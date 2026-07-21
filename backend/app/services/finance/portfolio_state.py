"""État du portefeuille dérivé du ledger et des positions manuelles.

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
        from sqlmodel import select

        from app.models.finance import FinanceSettings  # type: ignore
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
    from sqlmodel import select

    from app.models.finance import FinanceSettings
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
    if not txs:
        # Pas de ledger : l'utilisateur saisit des positions manuelles. On dérive
        # l'état (investi, P&L latent, valeur) de la table Position. Cash et P&L
        # réalisé restent 0 (non calculables sans historique de mouvements).
        state = _state_from_positions(session, get_tax_params(session))
        _state_cache.set("state", state)
        return state

    # Cours UNIQUEMENT pour les positions encore ouvertes : une position soldée
    # n'a pas besoin de prix (sa valeur est déjà réalisée), et un ticker fermé
    # peut être invalide côté Yahoo (ex. symbole T212 sans suffixe .PA) --
    # avant ce filtre, CHAQUE ticker jamais tradé était re-téléchargé à chaque
    # rafraîchissement de l'état, en pure perte (#spam "possibly delisted").
    tickers = open_position_tickers(txs)
    prix = get_prices(list(tickers), stale_ok=True) if tickers else {}
    state = compute_portfolio_state(txs, prix, get_tax_params(session))
    state = _merge_manual_positions(session, state)
    _state_cache.set("state", state)
    return state


def _state_from_positions(session, taxe: dict) -> dict:
    """État dérivé de la table Position (mode saisie manuelle, sans ledger)."""
    from sqlmodel import select

    from app.models.finance import Position
    from app.services.finance.prices import get_prices

    rows = list(session.exec(select(Position)).all())
    prix = get_prices([p.ticker for p in rows], stale_ok=True) if rows else {}

    positions = []
    pl_latent_total = 0.0
    investi = 0.0
    for pos in rows:
        q = float(pos.quantite or 0)
        acb = float(pos.pmu or 0.0)
        p = float(prix.get(pos.ticker, 0) or 0)
        valeur = p * q
        pl = (p - acb) * q if acb else 0.0
        pl_latent_total += pl
        investi += acb * q
        positions.append({
            "ticker": pos.ticker, "broker": pos.broker, "quantite": round(q, 6),
            "acb": round(acb, 2), "prix": round(p, 2), "valeur": round(valeur, 2),
            "pl_latent": round(pl, 2),
            "pl_pct": round((p / acb - 1) * 100, 2) if acb > 0 else 0.0,
        })

    valeur_totale = round(sum(pos["valeur"] for pos in positions), 2)
    denom = valeur_totale if valeur_totale != 0 else 1.0
    for pos in positions:
        pos["poids_pct"] = round(pos["valeur"] / denom * 100, 2)
    allocation = [
        {"label": pos["ticker"], "valeur": pos["valeur"], "poids_pct": pos["poids_pct"]}
        for pos in sorted(positions, key=lambda x: x["valeur"], reverse=True)
    ]

    taux_pv = float(taxe.get("taux_plus_value_pct", 0) or 0)
    taux_div = float(taxe.get("taux_dividende_pct", 0) or 0)
    return {
        "positions": positions,
        "cash_par_broker": {},
        "cash_total": 0.0,
        "investi_net": round(investi, 2),
        "valeur_totale": valeur_totale,
        "pl_realise": 0.0,
        "pl_latent_total": round(pl_latent_total, 2),
        "dividendes_total": 0.0,
        "dividendes_bruts": 0.0,
        "retenues_source": 0.0,
        "interets_bruts": 0.0,
        "interets_total": 0.0,
        "revenus_mobiliers_total": 0.0,
        "allocation": allocation,
        "taxes": {
            "base_pv": 0.0, "impot_pv": 0.0, "base_div": 0.0, "impot_div": 0.0,
            "total": 0.0, "taux_plus_value_pct": taux_pv, "taux_dividende_pct": taux_div,
        },
    }


def _merge_manual_positions(session, state: dict) -> dict:
    """Ajoute les positions manuelles absentes du ledger.

    Une ligne ledger gagne uniquement sur le même couple ``ticker, broker``.
    Cela permet de suivre quelques transactions sans faire disparaître les
    comptes encore maintenus manuellement.
    """
    from sqlmodel import select

    from app.models.finance import Position
    from app.services.finance.prices import get_prices

    existing = {
        (str(position["ticker"]).upper(), position.get("broker") or "default")
        for position in state["positions"]
    }
    manual_rows = []
    seen = set(existing)
    for position in session.exec(select(Position)).all():
        key = (position.ticker.upper(), position.broker or "default")
        if key in seen:
            continue
        seen.add(key)
        manual_rows.append(position)
    if not manual_rows:
        return state

    prices = get_prices([position.ticker for position in manual_rows], stale_ok=True)
    invested = 0.0
    unrealized = 0.0
    for position in manual_rows:
        quantity = float(position.quantite or 0)
        acb = float(position.pmu or 0)
        price = float(prices.get(position.ticker, 0) or 0)
        value = price * quantity
        pnl = (price - acb) * quantity if acb else 0.0
        invested += acb * quantity
        unrealized += pnl
        state["positions"].append(
            {
                "ticker": position.ticker,
                "broker": position.broker,
                "quantite": round(quantity, 6),
                "acb": round(acb, 2),
                "prix": round(price, 2),
                "valeur": round(value, 2),
                "pl_latent": round(pnl, 2),
                "pl_pct": round((price / acb - 1) * 100, 2) if acb > 0 else 0.0,
            }
        )

    state["investi_net"] = round(float(state["investi_net"]) + invested, 2)
    state["pl_latent_total"] = round(float(state["pl_latent_total"]) + unrealized, 2)
    state["valeur_totale"] = round(
        sum(position["valeur"] for position in state["positions"])
        + float(state["cash_total"]),
        2,
    )
    denominator = state["valeur_totale"] or 1.0
    for position in state["positions"]:
        position["poids_pct"] = round(position["valeur"] / denominator * 100, 2)
    state["allocation"] = [
        {
            "label": position["ticker"],
            "valeur": position["valeur"],
            "poids_pct": position["poids_pct"],
        }
        for position in sorted(
            state["positions"], key=lambda item: item["valeur"], reverse=True
        )
    ]
    if state["cash_total"] != 0:
        state["allocation"].append(
            {
                "label": "Cash",
                "valeur": state["cash_total"],
                "poids_pct": round(state["cash_total"] / denominator * 100, 2),
            }
        )
    return state


def open_position_tickers(transactions) -> set[str]:
    """Tickers dont la quantité nette (achats − ventes) est encore > 0.

    Seules ces positions ont besoin d'un cours actuel ; les dividendes et les
    positions soldées n'en ont pas (montants cash déjà réalisés).
    """
    qte: dict[str, float] = defaultdict(float)
    for t in transactions:
        typ = str(getattr(t, "type", "") or "").lower()
        ticker = (getattr(t, "ticker", "") or "").upper()
        if not ticker or ticker == "CASH":
            continue
        q = float(getattr(t, "quantite", 0) or 0)
        if typ == "achat":
            qte[ticker] += q
        elif typ == "vente":
            qte[ticker] -= q
    return {t for t, q in qte.items() if q > 1e-9}


def _montant(t) -> float:
    """Montant cash d'une ligne (cash : quantite=1, prix=montant ; sinon q*pu)."""
    q = getattr(t, "quantite", 0) or 0
    pu = getattr(t, "prix_unitaire", 0) or 0
    return (q * pu) if q else pu


def compute_portfolio_state(transactions, prix: dict[str, float], taxe: dict) -> dict:
    """Dérive l'état complet du portefeuille depuis les transactions.

    transactions : itérable d'objets avec attributs
        type (achat|vente|dividende|interet|depot|retrait|frais), ticker, broker,
        quantite, prix_unitaire, frais, date.
    prix : {ticker: cours_actuel}.
    taxe : {taux_plus_value_pct, taux_dividende_pct}.
    """
    txs = sorted(transactions, key=lambda t: (getattr(t, "date", None) or 0, getattr(t, "id", 0) or 0))

    book: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"qte": 0.0, "cout": 0.0})
    cash: dict[str, float] = defaultdict(float)
    realise = 0.0
    dividendes_bruts = 0.0
    retenues_source = 0.0
    dividendes_nets = 0.0
    interets_bruts = 0.0
    interets_nets = 0.0
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
            realise += (pu - acb) * q - frais
            b["cout"] -= acb * q
            b["qte"] -= q
            if b["qte"] < 1e-9:
                b["qte"] = 0.0
                b["cout"] = 0.0
            cash[broker] += q * pu - frais
        elif typ == "dividende":
            montant_stocke = getattr(t, "montant_brut", None)
            brut = float(montant_stocke) if montant_stocke is not None else _montant(t)
            retenue = float(getattr(t, "retenue_source", 0) or 0)
            net = brut - retenue - frais
            cash[broker] += net
            dividendes_bruts += brut
            retenues_source += retenue
            dividendes_nets += net
        elif typ == "interet":
            montant_stocke = getattr(t, "montant_brut", None)
            brut = float(montant_stocke) if montant_stocke is not None else _montant(t)
            net = brut - frais
            cash[broker] += net
            interets_bruts += brut
            interets_nets += net
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
    revenus_bruts = dividendes_bruts + interets_bruts
    impot_div = round(revenus_bruts * taux_div / 100, 2)

    return {
        "positions": positions,
        "cash_par_broker": {k: round(v, 2) for k, v in cash.items()},
        "cash_total": cash_total,
        "investi_net": round(depots - retraits, 2),
        "valeur_totale": valeur_totale,
        "pl_realise": round(realise, 2),
        "pl_latent_total": round(pl_latent_total, 2),
        "dividendes_total": round(dividendes_nets, 2),
        "dividendes_bruts": round(dividendes_bruts, 2),
        "retenues_source": round(retenues_source, 2),
        "interets_bruts": round(interets_bruts, 2),
        "interets_total": round(interets_nets, 2),
        "revenus_mobiliers_total": round(dividendes_nets + interets_nets, 2),
        "allocation": allocation,
        "taxes": {
            "base_pv": round(base_pv, 2),
            "impot_pv": impot_pv,
            "base_div": round(revenus_bruts, 2),
            "impot_div": impot_div,
            "total": round(impot_pv + impot_div, 2),
            "taux_plus_value_pct": taux_pv,
            "taux_dividende_pct": taux_div,
        },
    }
