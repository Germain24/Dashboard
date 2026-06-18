"""Import des relevés Wise (un fichier Excel par devise).

On ne garde que les transactions par carte (achats/remboursements), converties
en CAD. Les mouvements internes — conversions de devises, dépôts/top-ups,
transferts — sont exclus (ce ne sont pas des dépenses/revenus réels).

`parse_wise_rows` est pur (testable) ; `import_wise` lit l'Excel et convertit
via le service FX, puis alimente le budget.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.services.budget.transactions import create_transaction

# Colonnes de l'export Wise (ordre fixe) — accès positionnel (robuste aux accents).
_C_DATE, _C_MONTANT, _C_DEVISE, _C_DESC, _C_COMMERCANT, _C_INFO = 1, 3, 4, 5, 15, 22


def parse_wise_rows(
    rows: list[dict[str, Any]], *, convert: Callable[[float, str], float | None],
) -> list[tuple[dt.date, float, str]]:
    """Transactions carte (CARD) d'un relevé Wise, converties en CAD via `convert`.

    `convert(montant, devise) -> montant_cad | None`. Les lignes non-carte
    (conversions, dépôts, transferts) et non convertibles sont ignorées.
    """
    out: list[tuple[dt.date, float, str]] = []
    for r in rows:
        if r.get("info") != "CARD":
            continue
        try:
            montant = float(r["montant"])
        except (TypeError, ValueError):
            continue
        cad = convert(montant, str(r["devise"]))
        if cad is None:
            continue
        marchand = (str(r.get("commercant") or "").strip()
                    or str(r.get("description") or "").strip() or "Wise")
        out.append((r["date"], round(cad, 2), marchand))
    return out


def _read_wise_xlsx(data: bytes) -> list[dict[str, Any]]:
    """Lit un Excel Wise en lignes {date, montant, devise, description, commercant, info}."""
    import io

    import pandas as pd

    df = pd.read_excel(io.BytesIO(data))
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        raw_date = r.iloc[_C_DATE]
        date = raw_date.date() if hasattr(raw_date, "date") else raw_date
        rows.append({
            "date": date, "montant": r.iloc[_C_MONTANT], "devise": r.iloc[_C_DEVISE],
            "description": r.iloc[_C_DESC], "commercant": r.iloc[_C_COMMERCANT],
            "info": r.iloc[_C_INFO],
        })
    return rows


def _fx_to_cad(montant: float, devise: str) -> float | None:
    devise = (devise or "").upper()
    if devise == "CAD":
        return montant
    try:
        from app.services.finance.fx import convert as fx_convert
        return fx_convert(montant, devise, "CAD")
    except Exception:
        return None


def import_wise(session: Session, data: bytes, compte: str = "wise") -> dict[str, Any]:
    """Importe un relevé Wise (Excel) : transactions carte converties en CAD.

    Idempotent par (date, montant, marchand) sur le compte.
    """
    from sqlmodel import select

    from app.models.budget import BudgetTransaction

    parsed = parse_wise_rows(_read_wise_xlsx(data), convert=_fx_to_cad)
    existing = {
        (t.date, round(t.montant, 2), t.marchand)
        for t in session.exec(select(BudgetTransaction).where(BudgetTransaction.compte == compte)).all()
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
    return {"imported": imported, "skipped": skipped, "categorised": categorised,
            "parsed": len(parsed), "format": "wise"}
