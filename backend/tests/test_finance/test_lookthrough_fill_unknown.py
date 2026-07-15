"""Répartition proportionnelle du poids des tickers sans pays connu (ETC or/argent
physiques...) entre les pays déjà connus -- au lieu de 0% partout (invisible au
plafond MAX_COUNTRY_PCT) ou d'un seau "Inconnu" opaque en reporting."""

from app.services.finance.buffett.lookthrough import fill_unknown_countries


def test_unknown_ticker_gets_proportional_average_of_known():
    pays = {
        "A": {"France": 0.6, "Germany": 0.4},
        "B": {"France": 0.2, "United States": 0.8},
    }
    out = fill_unknown_countries(pays, ["A", "B", "GOLD"])
    # Moyenne (somme puis renormalisation) de A+B : France 0.8, Germany 0.4, US 0.8 -> total 2.0
    assert out["GOLD"] == {"France": 0.4, "Germany": 0.2, "United States": 0.4}
    assert sum(out["GOLD"].values()) == 1.0


def test_known_tickers_unchanged():
    pays = {"A": {"France": 1.0}}
    out = fill_unknown_countries(pays, ["A", "GOLD"])
    assert out["A"] == {"France": 1.0}


def test_all_unknown_returns_as_is_no_known_to_redistribute_from():
    out = fill_unknown_countries({}, ["GOLD", "SILVER"])
    assert out == {"GOLD": {}, "SILVER": {}}


def test_no_unknown_tickers_returns_unchanged():
    pays = {"A": {"France": 1.0}, "B": {"Germany": 1.0}}
    out = fill_unknown_countries(pays, ["A", "B"])
    assert out == {"A": {"France": 1.0}, "B": {"Germany": 1.0}}


def test_ticker_case_insensitive():
    pays = {"A.PA": {"France": 1.0}}
    out = fill_unknown_countries(pays, ["a.pa", "gold.l"])
    assert out["A.PA"] == {"France": 1.0}
    assert out["GOLD.L"] == {"France": 1.0}
