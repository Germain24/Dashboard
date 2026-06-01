"""Discrétisation de l'allocation optimale en ordres réels par broker.

Règle métier (CONV 4 — révision) :
- **Trading212** autorise les *pies* (fractions d'action) → montant € exact.
- **Tous les autres brokers** (BoursDirect, BoursDirect2, IBKR, …) n'autorisent
  que l'achat d'**actions entières** → on convertit le poids cible en un nombre
  entier d'actions à partir du budget du broker et du prix de l'action.
  Conséquence : une action peut représenter moins (ou plus) de 1 % du budget,
  ce que l'ancienne discrétisation par paliers de 1 % ne savait pas faire.
"""

from __future__ import annotations

import numpy as np

from .config import Config


def _clean(name) -> str:
    return "".join(filter(str.isalnum, str(name).upper()))


def is_fractional_broker(broker_name: str) -> bool:
    """True si le broker autorise les fractions d'action (pies).

    Seul Trading212 (toutes orthographes : Trading212, Tradding 212, T212…).
    """
    c = _clean(broker_name)
    return "TRADING212" in c or "TRADDING212" in c or c == "T212"


def latest_prices(close_df, tickers: list[str]) -> dict[str, float]:
    """Dernier prix de clôture connu par ticker depuis un DataFrame de prix."""
    prices: dict[str, float] = {}
    if close_df is None:
        return prices
    for t in tickers:
        try:
            if t in close_df.columns:
                serie = close_df[t].dropna()
                if len(serie):
                    prices[t] = float(serie.iloc[-1])
        except Exception:
            pass
    return prices


def discretize_allocation(
    tickers: list[str],
    weights,                 # np.ndarray [n_tickers x n_brokers] : fraction du capital TOTAL
    active_brokers: list[str],
    prices: dict[str, float],
    total_cap: float | None = None,
) -> list[dict]:
    """Convertit des poids continus en allocation exécutable par broker.

    Retourne une liste de dicts :
      {Ticker, Broker, shares (int|None), eur, prix, type ('pie'|'shares'),
       Poids total (%)}

    - Pies (Trading212) : shares=None, montant € exact (renormalisé au budget).
    - Actions entières  : shares = floor(€_cible / prix), puis le budget restant
      est rempli action par action sur les titres les plus sous-pondérés.
    """
    weights = np.asarray(weights, dtype=float)
    if weights.ndim == 1:
        weights = weights.reshape(len(tickers), len(active_brokers))
    num_t, num_b = len(tickers), len(active_brokers)
    if total_cap is None:
        total_cap = float(sum(Config.BUDGET_BROKERS.values())) or 1.0

    alloc: list[dict] = []
    for j, broker in enumerate(active_brokers):
        budget_j = float(Config.BUDGET_BROKERS.get(broker, 0.0))
        if budget_j <= 0:
            continue
        # € cible par ticker chez ce broker (depuis le poids continu)
        eur_target = {
            tickers[i]: max(float(weights[i, j]), 0.0) * total_cap
            for i in range(num_t)
        }
        total_target = sum(eur_target.values())
        if total_target <= 0:
            continue

        if is_fractional_broker(broker):
            # Pies : montant € exact, renormalisé pour utiliser tout le budget
            for i in range(num_t):
                t = tickers[i]
                e = eur_target[t] / total_target * budget_j
                if e <= 0.01:
                    continue
                alloc.append({
                    "Ticker": t, "Broker": broker, "shares": None,
                    "eur": round(e, 2), "prix": round(float(prices.get(t, 0) or 0), 4),
                    "type": "pie", "Poids total (%)": round(e / total_cap * 100, 4),
                })
            continue

        # Actions entières
        shares: dict[str, int] = {}
        for i in range(num_t):
            t = tickers[i]
            p = float(prices.get(t, 0) or 0)
            shares[t] = int(np.floor(eur_target[t] / p)) if (p > 0 and eur_target[t] > 0) else 0
        spent = sum(shares[t] * float(prices.get(t, 0) or 0) for t in shares)
        remaining = budget_j - spent

        # Remplir le budget restant : +1 action au titre le plus sous-pondéré qui rentre
        for _ in range(100000):
            if remaining <= 0:
                break
            best, best_gap = None, 0.0
            for i in range(num_t):
                t = tickers[i]
                p = float(prices.get(t, 0) or 0)
                if p <= 0 or eur_target[t] <= 0 or p > remaining + 1e-9:
                    continue
                gap = eur_target[t] - shares[t] * p   # sous-pondération en €
                if gap > best_gap:
                    best_gap, best = gap, t
            if best is None:
                break
            shares[best] += 1
            remaining -= float(prices.get(best, 0) or 0)

        for i in range(num_t):
            t = tickers[i]
            n = shares[t]
            if n <= 0:
                continue
            p = float(prices.get(t, 0) or 0)
            e = n * p
            alloc.append({
                "Ticker": t, "Broker": broker, "shares": int(n),
                "eur": round(e, 2), "prix": round(p, 4),
                "type": "shares", "Poids total (%)": round(e / total_cap * 100, 4),
            })
    return alloc
