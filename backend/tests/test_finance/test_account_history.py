"""Historique patrimoine par compte depuis les relevés (BP, Desjardins CSV, T212)."""

from __future__ import annotations

import datetime as dt

from app.services.finance.account_history import (
    aggregate_wise,
    build_daily_series,
    build_monthly_series,
    parse_bp_closing,
    parse_desjardins_csv_all,
    parse_desjardins_csv_solde,
    parse_westpac_statement,
)


def test_parse_desjardins_csv_all_one_point_per_day():
    content = (
        "815,DESJ,DB,2026/01/05,1,EPICERIE,,45.00,,,,,,1955.00\n"
        "815,DESJ,DB,2026/01/05,2,CAFE,,5.00,,,,,,1950.00\n"   # même jour → EOD
        "815,DESJ,DB,2026/01/20,3,PAIE,,,1500.00,,,,,3450.00\n"
    )
    pts = parse_desjardins_csv_all(content)
    assert pts == [(dt.date(2026, 1, 5), 1950.00), (dt.date(2026, 1, 20), 3450.00)]


def test_build_daily_series_carry_forward():
    pts = {"Desjardins": [(dt.date(2024, 1, 1), 100.0), (dt.date(2024, 1, 3), 130.0)]}
    out = build_daily_series(pts, [], today=dt.date(2024, 1, 4))
    assert out["dates"] == ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    assert out["series"]["Desjardins"] == [100.0, 100.0, 130.0, 130.0]   # report quotidien
    assert out["total"] == [100.0, 100.0, 130.0, 130.0]


def test_parse_westpac_statement():
    text = (
        "Opening Balance $0.00 Total Credits + $3,000.00 Total Debits - $1,925.57 "
        "Closing Balance         + $1,074.43\n"
        "Statement Period\n"
        "17 September 2024 - 30 September 2024736-022865 672\n"
    )
    d, v = parse_westpac_statement(text)
    assert d == dt.date(2024, 9, 30)   # fin de période
    assert v == 1074.43                # Closing Balance


def test_parse_westpac_none_without_period():
    assert parse_westpac_statement("Closing Balance + $10.00 mais pas de période") is None


def test_aggregate_wise_sums_currencies_with_carry_forward():
    # 1 devise étrangère = 0,5 €, EUR = 1:1.
    fx = lambda amt, dev: amt * (1.0 if dev == "EUR" else 0.5)
    per = {
        "EUR": [(dt.date(2024, 1, 1), 100.0), (dt.date(2024, 3, 1), 200.0)],
        "CAD": [(dt.date(2024, 2, 1), 40.0)],  # → 20 €
    }
    out = aggregate_wise(per, fx)
    assert out == [
        (dt.date(2024, 1, 1), 100.0),   # EUR 100 + CAD 0
        (dt.date(2024, 2, 1), 120.0),   # EUR 100 + CAD 20
        (dt.date(2024, 3, 1), 220.0),   # EUR 200 + CAD 20 (report)
    ]


# ── Banque Populaire : solde créditeur de clôture (marqué d'un *) ─────────────

_BP = """Votre relevé de compte n°11 au 29/11/2024
SOLDE CREDITEUR AU 31/10/2024  417,21 €
05/11 PRLV SEPA ONEY - 48,99 €
27/11 EUROVIR SEPA  200,00 €
SOLDE CREDITEUR AU 29/11/2024*  1 624,10 €
RECAPITULATIF
"""


def test_parse_bp_closing_balance():
    d, v = parse_bp_closing(_BP)
    assert d == dt.date(2024, 11, 29)
    assert v == 1624.10   # clôture (le *), pas l'ouverture ; espace = millier


def test_parse_bp_none_without_closing():
    assert parse_bp_closing("aucun solde ici") is None


# ── Desjardins AccèsD CSV : dernier solde (col 13) ───────────────────────────

_ACCESD = (
    "815,DESJ,DB,2026/01/05,1,EPICERIE,,45.00,,,,,,1955.00\n"
    "815,DESJ,DB,2026/01/20,2,PAIE,,,1500.00,,,,,3455.00\n"
)


def test_parse_desjardins_csv_solde_takes_latest_row():
    d, v = parse_desjardins_csv_solde(_ACCESD)
    assert d == dt.date(2026, 1, 20)
    assert v == 3455.00   # solde de la ligne la plus récente (col 13)


# ── Construction de la série mensuelle empilée ───────────────────────────────

def test_build_monthly_series_carry_forward_and_zero_before():
    pts = {"Banque Populaire": [(dt.date(2024, 1, 31), 100.0), (dt.date(2024, 3, 31), 150.0)]}
    manual = [("RealT", 500.0, dt.date(2024, 2, 15))]
    out = build_monthly_series(pts, manual, today=dt.date(2024, 3, 15))

    assert out["dates"] == ["2024-01-31", "2024-02-29", "2024-03-31"]   # fins de mois
    assert out["comptes"] == ["Banque Populaire", "RealT"]
    assert out["series"]["Banque Populaire"] == [100.0, 100.0, 150.0]   # report
    assert out["series"]["RealT"] == [0.0, 500.0, 500.0]                # 0 avant création
    assert out["total"] == [100.0, 600.0, 650.0]
