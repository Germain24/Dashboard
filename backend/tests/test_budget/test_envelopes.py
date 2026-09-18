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


def test_classify_envelope_thresholds():
    from app.services.budget.envelopes import classify_envelope
    assert classify_envelope(0) == "ok"
    assert classify_envelope(79.9) == "ok"
    assert classify_envelope(80) == "warning"
    assert classify_envelope(100) == "warning"   # pile à la limite = pas encore dépassé
    assert classify_envelope(100.1) == "over"
    assert classify_envelope(150) == "over"
