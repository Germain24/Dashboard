from app.services.journal.correlations import interpret, pearson


def test_pearson_perfect_positive():
    assert pearson([1, 2, 3], [2, 4, 6]) == 1.0


def test_pearson_perfect_negative():
    assert pearson([1, 2, 3], [6, 4, 2]) == -1.0


def test_pearson_zero_variance_is_none():
    assert pearson([1, 2, 3], [5, 5, 5]) is None


def test_pearson_too_few_points_is_none():
    assert pearson([1], [1]) is None


def test_interpret_strength_and_sign():
    assert interpret(0.75) == {"force": "forte", "signe": "positif"}
    assert interpret(-0.5) == {"force": "modérée", "signe": "négatif"}
    assert interpret(0.1) == {"force": "négligeable", "signe": "positif"}


from app.services.journal.correlations import correlate_series


def test_correlate_series_intersects_dates():
    mood = {"2026-06-01": 2.0, "2026-06-02": 4.0, "2026-06-03": 3.0}
    target = {"2026-06-01": 4.0, "2026-06-02": 8.0}  # 06-03 absent -> ignoré
    res = correlate_series(mood, target)
    assert res["n"] == 2
    assert res["r"] == 1.0
    assert res["force"] == "forte" and res["signe"] == "positif"


def test_correlate_series_insufficient():
    res = correlate_series({"2026-06-01": 2.0}, {"2026-06-01": 4.0})
    assert res["n"] == 1 and res["r"] is None and res["force"] == "indéterminée"
