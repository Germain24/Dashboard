"""Import / sync de la wishlist voyage depuis Voyage.xlsx (master)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.voyage import LieuVoyage

_COLS = {
    "nom": "Lieux",
    "ville": "Ville (ou ville la plus proche)",
    "pays": "Pays",
    "visite": "Visité",
    "aeroport_iata": "Aéroport (IATA)",
    "jours_min": "Jours min",
    "jours_max": "Jours max",
    "cout_jour_estime": "Coût/jour estimé",
}


def _clean_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_int(v: Any) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    return int(float(v))


def _clean_float(v: Any) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    return float(v)


def parse_voyage_xlsx(path: Path) -> list[dict]:
    """Lit la feuille 0 par en-têtes de colonnes (cf. `_COLS`).

    Les lignes sans `Lieux` sont ignorées. Les colonnes manquantes du fichier
    (ex. avant l'ajout des nouvelles colonnes) donnent des valeurs `None`.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    header = rows[0] if rows else []
    col_idx = {name: header.index(label) for name, label in _COLS.items() if label in header}

    def _cell(row: tuple, name: str):
        i = col_idx.get(name)
        return row[i] if i is not None and i < len(row) else None

    out: list[dict] = []
    for row in rows[1:]:
        nom = _clean_str(_cell(row, "nom"))
        if not nom:
            continue
        out.append({
            "nom": nom,
            "ville": _clean_str(_cell(row, "ville")),
            "pays": _clean_str(_cell(row, "pays")),
            "visite": bool(_cell(row, "visite")),
            "aeroport_iata": _clean_str(_cell(row, "aeroport_iata")),
            "jours_min": _clean_int(_cell(row, "jours_min")),
            "jours_max": _clean_int(_cell(row, "jours_max")),
            "cout_jour_estime": _clean_float(_cell(row, "cout_jour_estime")),
        })
    return out


def sync_voyage(session: Session, path: Path) -> dict:
    """Écrase la table cache `lieu_voyage` avec le contenu de l'Excel.

    Retourne `{"lieux": n, "incomplets": [noms]}` — un lieu non visité sans
    aéroport IATA ou sans fourchette de jours n'est pas utilisable comme
    candidat de planification.
    """
    rows = parse_voyage_xlsx(path)
    for old in session.exec(select(LieuVoyage)).all():
        session.delete(old)
    incomplets: list[str] = []
    for r in rows:
        session.add(LieuVoyage(**r))
        if not r["visite"] and (
            not r["aeroport_iata"] or r["jours_min"] is None or r["jours_max"] is None
        ):
            incomplets.append(r["nom"])
    session.commit()
    return {"lieux": len(rows), "incomplets": incomplets}
