"""Tests TDD — parseur de relevés Mastercard Desjardins (PDF, #256)."""

from __future__ import annotations

import datetime as dt

from app.services.budget.desjardins_pdf import parse_desjardins_mastercard

# Reproduit la sortie de pypdf : transactions concaténées, date JJMMJJMM sans
# espace, accents en mojibake, paiements en « CR » sans remise.
_TEXT = (
    "DATE DU RELEV�09012026\n"
    "5598 22** **** 800430012026       95,64     10,00\n"  # en-tête : date d'échéance JJMMAAAA → ignorée
    "24122412PATISSERIE NOTRE MAISO   MONTREAL     QC 2,00 %       15,40"
    "30123012PAIEMENT CAISSE         28,19CR"  # paiement → exclu (pas de remise)
    "01010201UBER CANADA/UBEREATS     TORONTO      ON 2,00 %       30,74"
    "07010701COSTCO WHOLESALE W527    MONTREAL     QC 0,50 %      243,36"
)


def test_parses_purchases_with_inferred_year():
    txns = parse_desjardins_mastercard(_TEXT)
    assert txns == [
        (dt.date(2025, 12, 24), -15.40, "PATISSERIE NOTRE MAISO MONTREAL QC"),
        (dt.date(2026, 1, 1), -30.74, "UBER CANADA/UBEREATS TORONTO ON"),
        (dt.date(2026, 1, 7), -243.36, "COSTCO WHOLESALE W527 MONTREAL QC"),
    ]


def test_excludes_payments():
    txns = parse_desjardins_mastercard(_TEXT)
    assert all("PAIEMENT CAISSE" not in m for _, _, m in txns)


def test_ignores_statement_header_dates():
    # La date d'échéance 30012026 (mois « 26 » invalide) ne doit pas créer de ligne.
    txns = parse_desjardins_mastercard(_TEXT)
    assert all(montant < 0 for _, montant, _ in txns)
    assert len(txns) == 3


def test_amounts_sum_matches_statement_total():
    # Le relevé annonce « Achats / débits + 771,55 » ; ici le sous-ensemble = 289,50.
    txns = parse_desjardins_mastercard(_TEXT)
    assert round(sum(-m for _, m, _ in txns), 2) == 289.50


def test_empty_without_statement_date():
    assert parse_desjardins_mastercard("aucune date de relevé ici") == []
