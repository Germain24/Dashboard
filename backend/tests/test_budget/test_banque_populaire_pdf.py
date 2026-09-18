"""Tests — parseur de relevés de compte chèque Banque Populaire (PDF)."""

from __future__ import annotations

import datetime as dt

from app.services.budget.banque_populaire_pdf import closing_balance, parse_banque_populaire

# Reproduit la sortie pypdf (mode plain) d'un relevé réel (avril 2025), section
# "DETAIL DES OPERATIONS" jusqu'au total des mouvements débiteurs.
_TEXT = """DATE
COMPTA
DATE
OPERATION
DATE
VALEURLIBELLE / REFERENCE MONTANT
SOLDE CREDITEUR AU 31/03/2025  794,88 €
02/04 PRLV SEPA PayPal Europe 0805ZRP 01/04 01/04 - 14,92 €
1041219275166/PAYPAL
46T22255KSGD2
03/04 010425 CB****5872 49B8LMK 02/04 02/04 - 10,46 €
Google CLOUD F8FR Paris
10,46EUR 1 EURO = 1,000000
07/04 PRLV SEPA ONEY BANQUE AC 0805QOX 04/04 04/04 - 48,99 €
TO=02228009964*TO=02228009964
29389DAB2C2248489C84FC2085089C67
07/04 PRLV SEPA BP GRAND OUEST 081VIGF 04/04 04/04 - 32,54 €
44494638669001
XP00000000000019702262
08/04 COTIS CRISTAL CONFORT 0022147 06/04 06/04 - 2,00 €F
XCCNV067 2025040600022147000001
CONTRAT CNV0028909612
23/04 210425 CB****5872 56E899I 22/04 22/04 - 41,68 €
JB HI FI WHITFOAU HILLARYS
74,00AUD 1 EURO = 1,775431
28/04 EUROVIR SEPA 25/04 25/04  200,00 €
VIR NAUDET
TOTAL DES MOUVEMENTS DEBITEURS - 150,59 €
TOTAL DES MOUVEMENTS CREDITEURS  200,00 €
SOLDE CREDITEUR AU 30/04/2025*  844,29 €
"""


def test_parses_all_operations_signed():
    txns = parse_banque_populaire(_TEXT)
    assert txns == [
        (dt.date(2025, 4, 2), -14.92, "PRLV SEPA PayPal Europe 0805ZRP"),
        (dt.date(2025, 4, 3), -10.46, "010425 CB****5872 49B8LMK"),
        (dt.date(2025, 4, 7), -48.99, "PRLV SEPA ONEY BANQUE AC 0805QOX"),
        (dt.date(2025, 4, 7), -32.54, "PRLV SEPA BP GRAND OUEST 081VIGF"),
        (dt.date(2025, 4, 8), -2.00, "COTIS CRISTAL CONFORT 0022147"),
        (dt.date(2025, 4, 23), -41.68, "210425 CB****5872 56E899I"),
        (dt.date(2025, 4, 28), 200.00, "EUROVIR SEPA"),
    ]


def test_debit_credit_totals_match_statement():
    txns = parse_banque_populaire(_TEXT)
    debits = sum(m for _, m, _ in txns if m < 0)
    credits = sum(m for _, m, _ in txns if m > 0)
    assert round(debits, 2) == -150.59
    assert round(credits, 2) == 200.00


def test_reference_lines_are_not_treated_as_transactions():
    txns = parse_banque_populaire(_TEXT)
    assert all("PAYPAL" not in libelle for _, _, libelle in txns)
    assert all("XCCNV" not in libelle for _, _, libelle in txns)


def test_closing_balance():
    assert closing_balance(_TEXT) == (dt.date(2025, 4, 30), 844.29)


def test_december_to_january_rollover():
    text = _TEXT.replace("SOLDE CREDITEUR AU 30/04/2025*  844,29", "SOLDE CREDITEUR AU 05/01/2026*  844,29")
    text = text.replace("28/04 EUROVIR SEPA 25/04 25/04  200,00", "28/12 EUROVIR SEPA 25/12 25/12  200,00")
    txns = parse_banque_populaire(text)
    dec_txn = next(t for t in txns if t[2] == "EUROVIR SEPA")
    assert dec_txn[0] == dt.date(2025, 12, 28)  # relevé de janvier 2026 -> opération de déc. 2025


def test_empty_text_returns_no_transactions():
    assert parse_banque_populaire("rien à voir ici") == []
