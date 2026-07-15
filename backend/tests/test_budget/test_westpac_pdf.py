"""Tests — parseur de relevés de compte Westpac (PDF, mode layout)."""

from __future__ import annotations

import datetime as dt

from app.services.budget.westpac_pdf import parse_westpac

# Reproduit la sortie pypdf (mode layout) d'un relevé réel (janvier 2025).
_TEXT = """DATETRANSACTION DESCRIPTION    DEBIT CREDITBALANCE

31/12/24STATEMENT OPENING BALANCE                1,814.33
02/01/25Debit Card Purchase McDonalds Beldon
          Beldon Aus                  9.56            1,804.77
02/01/25Debit Card Purchase Burns Beach Cfe &res
          Iluka Aus                 17.81            1,786.96
03/01/25Debit Card Purchase Dbs*anytime Fitness C
          Currambine Aus                23.95            1,763.01
"""

# La ligne "Mullaloo Beach H Fn Wages / Mbh" wrap sur DEUX lignes de
# continuation (pas une seule) avant le montant+solde.
_TEXT_CREDIT = """DATETRANSACTION DESCRIPTION    DEBIT CREDITBALANCE

31/12/24STATEMENT OPENING BALANCE                1,000.00
07/01/25Deposit-Salary Mcd Beldon Emp 01938             1,232.64          2,232.64
07/01/25Deposit-Salary Mullaloo Beach H Fn Wages
               Mbh                 1,358.90          3,591.54
"""

# La ligne CLOSING BALANCE apparaît parfois hors-séquence (artefact pypdf sur
# la dernière page) -- ne doit ni casser le parsing ni s'insérer comme opération.
_TEXT_MISPLACED_CLOSING = """DATETRANSACTION DESCRIPTION    DEBIT CREDITBALANCE

31/12/24STATEMENT OPENING BALANCE                1,094.70
31/01/25CLOSING BALANCE            559.00
30/01/25Debit Card Purchase Woolworths 4345 Beldon
          Aus            36.40          1,058.30
30/01/25Withdrawal Mobile 1497555 Tfr Westpac Lif
            70.00            988.30
"""


def test_parses_debits_with_wrapped_description():
    txns = parse_westpac(_TEXT)
    assert txns == [
        (dt.date(2025, 1, 2), -9.56, "Debit Card Purchase McDonalds Beldon Beldon Aus"),
        (dt.date(2025, 1, 2), -17.81, "Debit Card Purchase Burns Beach Cfe &res Iluka Aus"),
        (dt.date(2025, 1, 3), -23.95, "Debit Card Purchase Dbs*anytime Fitness C Currambine Aus"),
    ]


def test_parses_credits_single_and_multi_line():
    txns = parse_westpac(_TEXT_CREDIT)
    assert txns == [
        (dt.date(2025, 1, 7), 1232.64, "Deposit-Salary Mcd Beldon Emp 01938"),
        (dt.date(2025, 1, 7), 1358.90, "Deposit-Salary Mullaloo Beach H Fn Wages Mbh"),
    ]


def test_misplaced_closing_balance_line_ignored_without_breaking_chain():
    txns = parse_westpac(_TEXT_MISPLACED_CLOSING)
    assert txns == [
        (dt.date(2025, 1, 30), -36.40, "Debit Card Purchase Woolworths 4345 Beldon Aus"),
        (dt.date(2025, 1, 30), -70.00, "Withdrawal Mobile 1497555 Tfr Westpac Lif"),
    ]


def test_no_opening_balance_yields_no_transactions():
    assert parse_westpac("02/01/25Debit Card Purchase X\n   Aus   9.56   1,804.77\n") == []


def test_empty_text_returns_no_transactions():
    assert parse_westpac("rien à voir ici") == []
