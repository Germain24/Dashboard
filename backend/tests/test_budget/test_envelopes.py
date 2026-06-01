def test_envelope_pct_over_budget():
    budget, depense = 100.0, 150.0
    pct = (depense / budget * 100) if budget > 0 else 0
    assert pct == 150.0


def test_envelope_pct_zero_budget():
    budget, depense = 0.0, 50.0
    pct = (depense / budget * 100) if budget > 0 else 0
    assert pct == 0


def test_envelope_reste():
    assert 500.0 - 320.0 == 180.0
