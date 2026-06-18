"""Tests TDD — import des relevés Wise (un Excel par devise)."""

from __future__ import annotations

import datetime as dt

from app.services.budget.wise import parse_wise_rows


def _row(montant, devise, info, commercant="", description="", date=dt.date(2026, 4, 10)):
    return {"date": date, "montant": montant, "devise": devise, "info": info,
            "commercant": commercant, "description": description}


def _fake_convert(amount, base):
    rates = {"EUR": 1.5, "CAD": 1.0, "JPY": 0.0095}  # vers CAD
    r = rates.get(base)
    return round(amount * r, 2) if r is not None else None


def test_keeps_only_card_transactions_converted_to_cad():
    rows = [
        _row(-100.0, "EUR", "CARD", commercant="Shinzo Brand"),   # achat -> -150 CAD
        _row(-50.0, "CAD", "CARD", commercant="Tim Hortons"),     # achat CAD -> -50
        _row(20.0, "EUR", "CARD", commercant="Remboursement"),    # credit carte -> +30
        _row(-500.0, "EUR", "CONVERSION"),                        # change interne -> exclu
        _row(1000.0, "EUR", "DEPOSIT"),                           # top-up -> exclu
        _row(-30.0, "EUR", "TRANSFER"),                           # transfert -> exclu
    ]
    out = parse_wise_rows(rows, convert=_fake_convert)
    assert (dt.date(2026, 4, 10), -150.0, "Shinzo Brand") in out
    assert (dt.date(2026, 4, 10), -50.0, "Tim Hortons") in out
    assert (dt.date(2026, 4, 10), 30.0, "Remboursement") in out
    assert len(out) == 3   # uniquement les CARD


def test_uses_description_when_no_merchant_and_skips_unconvertible():
    rows = [
        _row(-10.0, "EUR", "CARD", description="Achat sans commercant"),
        _row(-10.0, "XYZ", "CARD", commercant="Devise inconnue"),   # convert -> None -> exclu
    ]
    out = parse_wise_rows(rows, convert=_fake_convert)
    assert out == [(dt.date(2026, 4, 10), -15.0, "Achat sans commercant")]
