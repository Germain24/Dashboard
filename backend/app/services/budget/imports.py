import csv
import datetime as dt
import hashlib
import io
import re
import unicodedata
from collections import Counter
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.events import Events, bus
from app.models.budget import BudgetTransaction
from app.services.budget.rules import apply_rules_to_transaction


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
    records, errors = [], 0
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        parsed = _parse_desjardins(row) if fmt == "desjardins" else _parse_generic(row)
        if parsed:
            date, montant, marchand = parsed
            records.append((date, montant, marchand, None))
        else:
            errors += 1
    result = _import_records(session, records, compte=compte, source=f"csv:{fmt}")
    return {**result, "errors": errors, "format": fmt}


# ─── OFX / QFX (relevés bancaires, #256) ─────────────────────────────────────

_OFX_TRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)


def _ofx_field(block: str, tag: str) -> str | None:
    """Extrait la valeur d'un élément OFX (SGML : pas de balise fermante)."""
    m = re.search(rf"<{tag}>([^<\r\n]*)", block, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_ofx_records(content: str) -> list[tuple[dt.date, float, str, str | None]]:
    """Parse les <STMTTRN> d'un relevé OFX/QFX (1.x SGML ou 2.x XML).

    Sans dépendance : on isole chaque transaction puis on lit DTPOSTED
    (AAAAMMJJ, éventuellement suivi de l'heure/fuseau), TRNAMT et NAME (à
    défaut MEMO). Les transactions incomplètes ou mal formées sont ignorées.
    """
    out: list[tuple[dt.date, float, str, str | None]] = []
    for block in _OFX_TRN_RE.findall(content):
        raw_date = _ofx_field(block, "DTPOSTED")
        raw_amt = _ofx_field(block, "TRNAMT")
        marchand = _ofx_field(block, "NAME") or _ofx_field(block, "MEMO") or ""
        external_id = _ofx_field(block, "FITID")
        if not raw_date or raw_amt is None:
            continue
        try:
            date = dt.datetime.strptime(raw_date[:8], "%Y%m%d").date()
            montant = float(raw_amt.replace(",", "."))
        except (ValueError, IndexError):
            continue
        out.append((date, montant, marchand, external_id))
    return out


def parse_ofx(content: str) -> list[tuple[dt.date, float, str]]:
    """Compatibility parser returning the public three-field transaction tuple."""
    return [(date, montant, marchand) for date, montant, marchand, _ in _parse_ofx_records(content)]


def import_ofx(session: Session, content: str, compte: str = "principal") -> dict:
    """Importe un relevé OFX/QFX en transactions (catégorisation auto via #115)."""
    result = _import_records(session, _parse_ofx_records(content), compte=compte, source="ofx")
    return {**result, "errors": 0, "format": "ofx"}


def _looks_like_ofx(content: str) -> bool:
    head = content.lstrip()[:512].upper()
    return head.startswith("OFXHEADER") or "<OFX>" in head


# ─── Export CSV AccèsD Desjardins (compte débit) ─────────────────────────────
# 14 colonnes sans en-tête : 0 caisse, 1 folio, 2 type, 3 date (AAAA/MM/JJ),
# 4 séquence, 5 description, 7 retrait (dépense), 8 dépôt (revenu), 13 solde.
# Transferts internes (entre comptes) et paiements de la carte exclus.
_ACCESD_SKIP = re.compile(
    r"Virement\s*-\s*Acc\S*\s*Internet\s*/\s*(a|à|de)\s*(EOP|ET\s*1)"
    r"|Virement automatique au compte"
    r"|Remises?\s*Mastercard"
    r"|Virement Interac.*Germain\s*De\s*Sou",   # virements vers/depuis soi-même
    re.IGNORECASE,
)
_ACCESD_DATE = re.compile(r"\d{4}/\d{2}/\d{2}$")


def _looks_like_accesd(content: str) -> bool:
    for row in csv.reader(io.StringIO(content)):
        if not any(c.strip() for c in row):
            continue
        return len(row) >= 14 and bool(_ACCESD_DATE.match(row[3].strip()))
    return False


def _parse_desjardins_accesd_records(
    content: str,
) -> list[tuple[dt.date, float, str, str | None]]:
    """Parse rows and preserve AccèsD's account/sequence reference as its source ID."""
    out: list[tuple[dt.date, float, str, str | None]] = []
    for row in csv.reader(io.StringIO(content)):
        if len(row) < 14:
            continue
        try:
            date = dt.datetime.strptime(row[3].strip(), "%Y/%m/%d").date()
        except ValueError:
            continue
        desc = re.sub(r"\s+", " ", row[5]).strip()
        retrait, depot = row[7].strip(), row[8].strip()
        if depot:
            montant = float(depot.replace(",", ""))
        elif retrait:
            montant = -float(retrait.replace(",", ""))
        else:
            continue
        if not desc or _ACCESD_SKIP.search(desc):
            continue
        # Folio + date + sequence are stable within an AccèsD account export.
        external_id = ":".join((row[0].strip(), row[1].strip(), row[3].strip(), row[4].strip()))
        out.append((date, round(montant, 2), desc, external_id))
    return out


def parse_desjardins_accesd(content: str) -> list[tuple[dt.date, float, str]]:
    """Parse an AccèsD export while preserving the public tuple shape."""
    return [(date, amount, merchant) for date, amount, merchant, _ in _parse_desjardins_accesd_records(content)]


def import_accesd(session: Session, content: str, compte: str = "desjardins-debit") -> dict:
    """Importe un export CSV AccèsD dans le budget (catégorisation #115)."""
    result = _import_records(
        session, _parse_desjardins_accesd_records(content), compte=compte,
        source="desjardins-accesd",
    )
    return {**result, "errors": 0, "format": "desjardins-debit"}


def _merchant_key(marchand: str) -> str:
    normalized = unicodedata.normalize("NFKC", marchand or "")
    return " ".join(normalized.split()).casefold()


def _semantic_key(
    date: dt.date, montant: float, marchand: str, compte: str, devise: str,
) -> tuple[dt.date, int, str, str, str]:
    cents = int(Decimal(str(montant)).quantize(Decimal("0.01")) * 100)
    return date, cents, _merchant_key(marchand), compte.strip().casefold(), devise.upper()


def _fingerprint(source: str, compte: str, semantic: tuple, external_id: str | None, occurrence: int) -> str:
    # OFX FITID and AccèsD sequence references survive export formatting changes.
    # Sources without transaction IDs use normalized values plus the occurrence
    # number, preserving two genuinely repeated same-day purchases in one file.
    identity = f"id:{external_id.strip()}" if external_id and external_id.strip() else f"row:{semantic}:{occurrence}"
    key = "\0".join((source, compte.strip().casefold(), identity))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _create_imported_transaction(
    session: Session, *, date: dt.date, montant: float, marchand: str, compte: str,
    devise: str, source: str, external_id: str | None, fingerprint: str,
) -> BudgetTransaction | None:
    """Insert transaction and source fingerprint in the same database commit.

    This mirrors create_transaction's categorization and event behavior, while
    including the unique fingerprint before commit to close the duplicate race.
    """
    description = ""
    category_id = apply_rules_to_transaction(session, f"{marchand} {description}")
    if category_id is None:
        from app.services.budget.investment_flows import default_investment_category_id

        category_id = default_investment_category_id(session, f"{marchand} {description} {compte}")

    transaction = BudgetTransaction(
        date=date, montant=montant, marchand=marchand, description=description,
        category_id=category_id, compte=compte, devise=devise, auto=False, tags=[],
        import_source=source, import_external_id=external_id, import_fingerprint=fingerprint,
    )
    session.add(transaction)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # A concurrent import may have inserted this exact fingerprint first.
        duplicate = session.exec(
            select(BudgetTransaction.id).where(BudgetTransaction.import_fingerprint == fingerprint)
        ).first()
        if duplicate is not None:
            return None
        raise
    session.refresh(transaction)
    bus.emit(
        Events.BUDGET_TRANSACTION_CREATED,
        id=transaction.id,
        montant=transaction.montant,
        marchand=transaction.marchand,
        category_id=transaction.category_id,
        date=transaction.date.isoformat(),
    )
    return transaction


def _import_records(
    session: Session,
    records: list[tuple[dt.date, float, str, str | None]],
    *,
    compte: str,
    source: str,
    devise: str = "CAD",
) -> dict:
    """Import records idempotently while preserving same-day duplicate purchases."""
    if not records:
        return {"imported": 0, "skipped": 0, "categorised": 0, "parsed": 0}

    existing = session.exec(
        select(BudgetTransaction).where(BudgetTransaction.compte == compte)
    ).all()
    fingerprints = {row.import_fingerprint for row in existing if row.import_fingerprint}
    # This semantic counter is also a compatibility bridge for transactions that
    # predate fingerprint columns. It does not modify those historic rows.
    semantic_counts = Counter(
        _semantic_key(row.date, row.montant, row.marchand, row.compte, row.devise)
        for row in existing
    )
    occurrences: Counter = Counter()
    imported = skipped = categorised = 0

    for date, montant, marchand, external_id in records:
        semantic = _semantic_key(date, montant, marchand, compte, devise)
        occurrence = occurrences[semantic]
        occurrences[semantic] += 1
        fingerprint = _fingerprint(source, compte, semantic, external_id, occurrence)
        if fingerprint in fingerprints or semantic_counts[semantic] > occurrence:
            skipped += 1
            continue

        transaction = _create_imported_transaction(
            session, date=date, montant=montant, marchand=marchand, compte=compte,
            devise=devise, source=source, external_id=external_id, fingerprint=fingerprint,
        )
        if transaction is None:
            skipped += 1
            fingerprints.add(fingerprint)
            semantic_counts[semantic] += 1
            continue

        imported += 1
        fingerprints.add(fingerprint)
        semantic_counts[semantic] += 1
        if transaction.category_id is not None:
            categorised += 1

    return {"imported": imported, "skipped": skipped, "categorised": categorised, "parsed": len(records)}


def import_transactions(session: Session, content: str, compte: str = "principal") -> dict:
    """Point d'entrée unique : détecte OFX/QFX et CSV AccèsD, sinon CSV générique."""
    if _looks_like_ofx(content):
        return import_ofx(session, content, compte)
    if _looks_like_accesd(content):
        compte = "desjardins-debit" if compte == "principal" else compte
        return import_accesd(session, content, compte)
    return import_csv(session, content, compte)
