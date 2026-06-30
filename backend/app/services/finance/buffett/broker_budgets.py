"""Budgets par broker dérivés des soldes RÉELS des comptes (account_balances.json).

L'optimiseur répartit le capital au prorata du budget de chaque broker. Plutôt que
des montants statiques, on lit les soldes réels importés (relevés Trading212,
BourseDirect…) et on les superpose aux valeurs statiques (repli si pas de solde live).
"""

from __future__ import annotations

# Clé de account_balances.json (minuscule) -> clé de Config.BUDGET_BROKERS.
# 'boursedirect' vise le compte principal (BoursDirect2).
_ACCOUNT_TO_BROKER = {
    "trading212": "Trading212",
    "t212": "Trading212",
    "boursedirect": "BoursDirect2",
    "boursedirect2": "BoursDirect2",
    "boursedirect1": "BoursDirect",
}


def compute_budgets(static: dict, balances: dict) -> dict:
    """Superpose les soldes live (``balances``) sur les budgets ``static``.

    ``balances`` : {compte_minuscule: {"solde": float, ...}} (account_balances.json).
    Un compte sans solde live garde sa valeur statique.
    """
    out = dict(static)
    for acct, info in (balances or {}).items():
        broker = _ACCOUNT_TO_BROKER.get(str(acct).strip().lower())
        if broker is None or broker not in out:
            continue
        try:
            out[broker] = round(float(info.get("solde")), 2)
        except (TypeError, ValueError):
            pass
    return out


def apply_live_broker_budgets() -> dict:
    """Met à jour ``Config.BUDGET_BROKERS`` avec les soldes live. Best-effort.

    Renvoie les budgets effectifs. Appelé juste avant l'optimisation.
    """
    from .config import Config
    try:
        from app.services.finance.account_balances import get_balances
        budgets = compute_budgets(dict(Config.BUDGET_BROKERS), get_balances())
        Config.BUDGET_BROKERS = budgets
        return budgets
    except Exception as e:  # pragma: no cover - réseau/IO
        print(f"[broker_budgets] soldes live non appliqués ({e}) — budgets statiques")
        return dict(Config.BUDGET_BROKERS)
