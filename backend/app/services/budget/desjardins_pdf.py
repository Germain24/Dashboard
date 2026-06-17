"""Import des relevés Mastercard Desjardins en PDF (#256).

pypdf concatène toutes les transactions sur une même ligne, sans espace dans la
date (« 24122412PATISSERIE… QC 2,00 % 15,40 »). On délimite donc chaque
transaction sur son préfixe de date JJMMJJMM (8 chiffres suivis d'une lettre,
avec jours ≤ 31 et mois ≤ 12 — ce qui écarte les dates d'en-tête en JJMMAAAA),
puis on lit la remise « X,XX % » et le montant. Les paiements (« PAIEMENT
CAISSE … CR ») n'ont pas de remise et sont donc naturellement exclus.

`parse_desjardins_mastercard` est pur (testable sur le texte extrait) ;
`import_desjardins_pdf` lit le PDF et alimente le budget (catégorisation #115).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlmodel import Session, select

from app.models.budget import BudgetTransaction
from app.services.budget.transactions import create_transaction

_PREFIX_RE = re.compile(r"(\d{2})(\d{2})(\d{2})(\d{2})(?=[A-Za-zÀ-ÿ])")
_AMOUNT_RE = re.compile(r"(\d{1,2},\d{2})\s*%\s+(\d{1,3}(?:[ ]\d{3})*,\d{2})")
_RELEVE_RE = re.compile(r"DATE DU RELEV.{0,3}?(\d{2})(\d{2})(\d{4})")


def _to_float(montant: str) -> float:
    return float(montant.replace(" ", "").replace(",", "."))


def _valid_dates(jt: int, mt: int, ji: int, mi: int) -> bool:
    return 1 <= jt <= 31 and 1 <= mt <= 12 and 1 <= ji <= 31 and 1 <= mi <= 12


def parse_desjardins_mastercard(text: str) -> list[tuple[dt.date, float, str]]:
    """Extrait les achats (débits) d'un relevé Mastercard Desjardins.

    Renvoie ``[(date, montant<0, marchand)]``. L'année est déduite de la date du
    relevé : une transaction postérieure au relevé appartient à l'année passée
    (cas décembre→janvier). Les paiements (sans remise %) sont exclus.
    """
    rel = _RELEVE_RE.search(text)
    if not rel:
        return []
    stmt = dt.date(int(rel.group(3)), int(rel.group(2)), int(rel.group(1)))

    prefixes = [
        pm for pm in _PREFIX_RE.finditer(text)
        if _valid_dates(int(pm.group(1)), int(pm.group(2)), int(pm.group(3)), int(pm.group(4)))
    ]

    out: list[tuple[dt.date, float, str]] = []
    for i, pm in enumerate(prefixes):
        jt, mt = int(pm.group(1)), int(pm.group(2))
        end = prefixes[i + 1].start() if i + 1 < len(prefixes) else len(text)
        chunk = text[pm.end():end]
        am = _AMOUNT_RE.search(chunk)
        if not am:
            continue  # paiement (CR, sans remise) ou ligne non-transaction → exclu
        marchand = re.sub(r"\s+", " ", chunk[: am.start()]).strip()
        if not marchand:
            continue
        try:
            d = dt.date(stmt.year, mt, jt)
        except ValueError:
            continue
        if d > stmt:  # transaction de l'année précédente (décembre → janvier)
            try:
                d = dt.date(stmt.year - 1, mt, jt)
            except ValueError:
                continue
        out.append((d, -_to_float(am.group(2)), marchand))
    return out


def extract_pdf_text(data: bytes) -> str:
    """Texte concaténé de toutes les pages d'un PDF (via pypdf)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def import_desjardins_pdf(
    session: Session, data: bytes, compte: str = "desjardins-mc",
) -> dict[str, Any]:
    """Importe un relevé Mastercard Desjardins (PDF) dans le budget.

    Idempotent best-effort : une transaction identique (date, montant, marchand)
    déjà présente sur ce compte est ignorée (réimport sans doublon).
    """
    parsed = parse_desjardins_mastercard(extract_pdf_text(data))
    existing = {
        (t.date, round(t.montant, 2), t.marchand)
        for t in session.exec(
            select(BudgetTransaction).where(BudgetTransaction.compte == compte)
        ).all()
    }
    imported, skipped, categorised = 0, 0, 0
    for date, montant, marchand in parsed:
        key = (date, round(montant, 2), marchand)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        t = create_transaction(session, date=date, montant=montant, marchand=marchand, compte=compte)
        imported += 1
        if t.category_id is not None:
            categorised += 1
    return {
        "imported": imported, "skipped": skipped, "categorised": categorised,
        "parsed": len(parsed), "format": "desjardins-pdf",
    }
