import csv
import datetime as dt
import io
import re

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
    imported, errors, categorised = 0, 0, 0
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        parsed = _parse_desjardins(row) if fmt == "desjardins" else _parse_generic(row)
        if parsed:
            date, montant, marchand = parsed
            # create_transaction applique déjà les règles de catégorisation (#115).
            t = create_transaction(session, date=date, montant=montant, marchand=marchand, compte=compte)
            imported += 1
            if t.category_id is not None:
                categorised += 1
        else:
            errors += 1
    return {"imported": imported, "errors": errors, "categorised": categorised, "format": fmt}


# ─── OFX / QFX (relevés bancaires, #256) ─────────────────────────────────────

_OFX_TRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)


def _ofx_field(block: str, tag: str) -> str | None:
    """Extrait la valeur d'un élément OFX (SGML : pas de balise fermante)."""
    m = re.search(rf"<{tag}>([^<\r\n]*)", block, re.IGNORECASE)
    return m.group(1).strip() if m else None


def parse_ofx(content: str) -> list[tuple[dt.date, float, str]]:
    """Parse les <STMTTRN> d'un relevé OFX/QFX (1.x SGML ou 2.x XML).

    Sans dépendance : on isole chaque transaction puis on lit DTPOSTED
    (AAAAMMJJ, éventuellement suivi de l'heure/fuseau), TRNAMT et NAME (à
    défaut MEMO). Les transactions incomplètes ou mal formées sont ignorées.
    """
    out: list[tuple[dt.date, float, str]] = []
    for block in _OFX_TRN_RE.findall(content):
        raw_date = _ofx_field(block, "DTPOSTED")
        raw_amt = _ofx_field(block, "TRNAMT")
        marchand = _ofx_field(block, "NAME") or _ofx_field(block, "MEMO") or ""
        if not raw_date or raw_amt is None:
            continue
        try:
            date = dt.datetime.strptime(raw_date[:8], "%Y%m%d").date()
            montant = float(raw_amt.replace(",", "."))
        except (ValueError, IndexError):
            continue
        out.append((date, montant, marchand))
    return out


def import_ofx(session: Session, content: str, compte: str = "principal") -> dict:
    """Importe un relevé OFX/QFX en transactions (catégorisation auto via #115)."""
    imported, categorised = 0, 0
    for date, montant, marchand in parse_ofx(content):
        t = create_transaction(session, date=date, montant=montant, marchand=marchand, compte=compte)
        imported += 1
        if t.category_id is not None:
            categorised += 1
    return {"imported": imported, "errors": 0, "categorised": categorised, "format": "ofx"}


def _looks_like_ofx(content: str) -> bool:
    head = content.lstrip()[:512].upper()
    return head.startswith("OFXHEADER") or "<OFX>" in head


def import_transactions(session: Session, content: str, compte: str = "principal") -> dict:
    """Point d'entrée unique : détecte OFX/QFX, sinon délègue au parseur CSV."""
    if _looks_like_ofx(content):
        return import_ofx(session, content, compte)
    return import_csv(session, content, compte)
