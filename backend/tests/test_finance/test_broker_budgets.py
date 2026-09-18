"""Budgets brokers dérivés des soldes RÉELS (account_balances.json)."""


def test_compute_budgets_overlays_live_balances():
    from app.services.finance.buffett.broker_budgets import compute_budgets
    static = {"Trading212": 733.70, "BoursDirect": 0.0, "BoursDirect2": 24472.0}
    balances = {"trading212": {"solde": 903.80, "devise": "EUR"}}
    out = compute_budgets(static, balances)
    assert out["Trading212"] == 903.80         # solde live utilisé
    assert out["BoursDirect2"] == 24472.0       # pas de solde live -> statique
    assert out["BoursDirect"] == 0.0


def test_compute_budgets_boursedirect_live_overrides_main_account():
    from app.services.finance.buffett.broker_budgets import compute_budgets
    static = {"Trading212": 733.70, "BoursDirect": 0.0, "BoursDirect2": 24472.0}
    balances = {"trading212": {"solde": 903.80}, "boursedirect": {"solde": 25000.0}}
    out = compute_budgets(static, balances)
    assert out["Trading212"] == 903.80
    assert out["BoursDirect2"] == 25000.0       # 'boursedirect' -> compte principal


def test_compute_budgets_no_balances_returns_static():
    from app.services.finance.buffett.broker_budgets import compute_budgets
    static = {"Trading212": 733.70, "BoursDirect2": 24472.0}
    assert compute_budgets(static, {}) == static
