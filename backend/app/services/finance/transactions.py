"""CRUD transactions + import CSV broker (Trading 212, Bourse Direct)."""

from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.finance import Transaction


def list_transactions(
    session: Session,
    ticker: Optional[str] = None,
    broker: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    limit: int = 500,
) -> list[Transaction]:
    q = select(Transaction).order_by(Transaction.date.desc())
    if ticker:
        q = q.where(Transaction.ticker == ticker.upper())
    if broker:
        q = q.where(Transaction.broker == broker)
    if date_from:
        q = q.where(Transaction.date >= dt.datetime.combine(date_from, dt.time.min))
    if date_to:
        q = q.where(Transaction.date <= dt.datetime.combine(date_to, dt.time.max))
    return list(session.exec(q.limit(limit)).all())


def create_transaction(session: Session, data: dict) -> Transaction:
    tx = Transaction(**data)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def delete_transaction(session: Session, tx_id: int) -> bool:
    tx = session.get(Transaction, tx_id)
    if not tx:
        return False
    session.delete(tx)
    session.commit()
    return True


# ── Parseurs CSV broker ────────────────────────────────────────────────────

def _parse_trading212_row(row: dict) -> Optional[dict]:
    """Ligne CSV Trading 212 → dict Transaction."""
    try:
        action = str(row.get("Action", "")).lower()
        if "buy" in action:
            type_ = "achat"
        elif "sell" in action:
            type_ = "vente"
        elif "dividend" in action:
            type_ = "dividende"
        else:
            return None
        return {
            "date": dt.datetime.fromisoformat(row.get("Time", "").replace("Z", "")),
            "ticker": str(row.get("Ticker", "")).strip().upper(),
            "broker": "Trading212",
            "type": type_,
            "quantite": float(row.get("No. of shares", 0) or 0),
            "prix_unitaire": float(row.get("Price / share", 0) or 0),
            "devise": str(row.get("Currency (Price / share)", "EUR")),
            "frais": float(row.get("Currency conversion fee", 0) or 0),
        }
    except Exception:
        return None


def _parse_boursedirect_row(row: dict) -> Optional[dict]:
    """Ligne CSV Bourse Direct → dict Transaction."""
    try:
        sens = str(row.get("Sens", "")).upper()
        if "ACHAT" in sens or "A" == sens:
            type_ = "achat"
        elif "VENTE" in sens or "V" == sens:
            type_ = "vente"
        else:
            return None
        date_str = row.get("Date opération", "") or row.get("Date", "")
        try:
            date_ = dt.datetime.strptime(date_str.strip(), "%d/%m/%Y")
        except Exception:
            date_ = dt.datetime.fromisoformat(date_str.strip())
        return {
            "date": date_,
            "ticker": str(row.get("Code ISIN", row.get("Libellé", ""))).strip().upper(),
            "broker": "BoursDirect",
            "type": type_,
            "quantite": float(str(row.get("Quantité", 0)).replace(",", ".") or 0),
            "prix_unitaire": float(str(row.get("Cours", 0)).replace(",", ".") or 0),
            "devise": "EUR",
            "frais": float(str(row.get("Frais", 0)).replace(",", ".") or 0),
        }
    except Exception:
        return None


def import_csv(session: Session, content: str, broker_hint: str = "auto") -> dict:
    """Importe des transactions depuis un CSV broker.

    broker_hint : 'trading212' | 'boursedirect' | 'auto' (détection automatique).
    Retourne {"imported": N, "skipped": N, "errors": [...]}.
    """
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return {"imported": 0, "skipped": 0, "errors": ["CSV vide"]}

    # Détection automatique du broker
    headers = set(rows[0].keys())
    if broker_hint == "auto":
        if "Action" in headers and "No. of shares" in headers:
            broker_hint = "trading212"
        elif "Sens" in headers or "Quantité" in headers:
            broker_hint = "boursedirect"
        else:
            return {"imported": 0, "skipped": 0, "errors": ["Format CSV non reconnu"]}

    parser = _parse_trading212_row if broker_hint == "trading212" else _parse_boursedirect_row
    imported = skipped = 0
    errors: list[str] = []

    for i, row in enumerate(rows):
        parsed = parser(row)
        if not parsed:
            skipped += 1
            continue
        if not parsed.get("ticker") or not parsed.get("quantite") or parsed["quantite"] == 0:
            skipped += 1
            continue
        tx = Transaction(**parsed)
        session.add(tx)
        try:
            session.commit()
            imported += 1
        except Exception as e:
            session.rollback()
            errors.append(f"Ligne {i+2}: {e}")
            skipped += 1

    return {"imported": imported, "skipped": skipped, "errors": errors}
