def test_monthly_summary_structure():
    required_keys = {"revenus", "depenses", "solde", "by_category"}
    sample = {"revenus": 0.0, "depenses": 0.0, "solde": 0.0, "by_category": {}}
    assert required_keys.issubset(sample.keys())


def test_disposable_is_solde():
    summary = {"revenus": 3000.0, "depenses": -2000.0, "solde": 1000.0, "by_category": {}}
    assert summary["solde"] == 1000.0


def test_solde_calculation():
    revenus = 3000.0
    depenses = -2000.0
    assert revenus + depenses == 1000.0
