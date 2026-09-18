"""Import / sync de l'objectif garde-robe depuis Vetements.xlsx (master)."""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models.garderobe import ObjectifType
from app.services.garderobe.objectif import build_echelle


def parse_objectif_xlsx(path: Path) -> list[dict]:
    """Lit la feuille 0 : ligne 0 = en-tête, lignes 1+ = types.

    Colonne A = nom du type, B = quantité objectif, C+ = marches Q/P → Max.
    Les lignes sans nom sont ignorées.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    out: list[dict] = []
    ordre = 0
    for row in rows[1:]:  # saute l'en-tête
        nom = row[0] if row else None
        if not nom or not str(nom).strip():
            continue
        quantite = int(row[1] or 0)
        echelle = build_echelle(list(row[2:]))
        out.append(
            {
                "nom": str(nom).strip(),
                "ordre": ordre,
                "quantite_objectif": quantite,
                "echelle": echelle,
            }
        )
        ordre += 1
    return out


def sync_objectif(session: Session, path: Path) -> int:
    """Écrase la table cache `objectif_type` avec le contenu de l'Excel."""
    rows = parse_objectif_xlsx(path)
    for old in session.exec(select(ObjectifType)).all():
        session.delete(old)
    for r in rows:
        session.add(ObjectifType(**r))
    session.commit()
    return len(rows)
