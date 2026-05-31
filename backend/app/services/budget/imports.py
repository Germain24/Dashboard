import csv
import io
import datetime as dt
from sqlmodel import Session
from app.services.budget.transactions import create_transaction


def _detect_format(headers: list[str]) -> str:
    h = [h.lower().strip() for h in headers]
    if "débit" in h or "debit" in h:
        return "desjardins"
    if "cad$" in h or "cad" in h:
        return "rbc"
    return "generic"


def _parse_desjardins(row: list[str]) -> tuple[dt.date, float, str] | None:
    try:
        date = dt.datetime.strptime(row[0].strip(), "%Y-%m-%d").date()
        debit = float(row[2].replace(",", "").strip()) if row[2].strip() else 0
        credit = float(row[3].replace(",", "").strip()) if row[3].strip() else 0
        return date, credit - debit, row[1].strip()
    except (ValueError, IndexError):
        return None


def _parse_generic(row: list[str]) -> tuple[dt.date, float, str] | None:
    try:
        date = dt.datetime.strptime(row[0].strip(), "%Y-%m-%d").date()
        montant = float(row[2].replace(",", "").strip())
        return date, montant, row[1].strip()
    except (ValueError, IndexError):
        return None


def import_csv(session: Session, content: str, compte: str = "principal") -> dict:
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return {"imported": 0, "errors": 0}
    fmt = _detect_format(rows[0])
    imported, errors = 0, 0
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        parsed = _parse_desjardins(row) if fmt == "desjardins" else _parse_generic(row)
        if parsed:
            date, montant, marchand = parsed
            create_transaction(session, date=date, montant=montant, marchand=marchand, compte=compte)
            imported += 1
        else:
            errors += 1
    return {"imported": imported, "errors": errors, "format": fmt}
