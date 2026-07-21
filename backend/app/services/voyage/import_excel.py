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
    "ordre": "Ordre",
    "aeroport_iata": "Aéroport (IATA)",
    "jours_min": "Jours min",
    "jours_max": "Jours max",
    "cout_jour_estime": "Coût/jour estimé",
    "progression": "Progression",
    "priorite": "Priorité",
    "cout_activite": "Coût activité",
    "cout_transport_local": "Transport local",
    "mois_disponibles": "Mois disponibles",
    "cout_hebergement_jour": "Coût hébergement/jour",
    "cout_nourriture_jour": "Coût nourriture/jour",
    "statut": "Statut",
    "raison_indisponible": "Raison indisponible",
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


def _infer_progression(nom: str, ordre: int | None) -> str | None:
    """Compatibilité avec le fichier actuel, qui a `Ordre` mais pas encore
    `Progression`. Les groupes explicites dans Excel restent prioritaires."""
    if ordre is None:
        return None
    n = nom.casefold()
    if any(token in n for token in ("marathon", "run", "spartathlon")):
        return "course"
    return "montagne"


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
        ordre = _clean_int(_cell(row, "ordre"))
        progression = _clean_str(_cell(row, "progression"))
        out.append({
            "nom": nom,
            "ville": _clean_str(_cell(row, "ville")),
            "pays": _clean_str(_cell(row, "pays")),
            "visite": bool(_cell(row, "visite")),
            "aeroport_iata": _clean_str(_cell(row, "aeroport_iata")),
            "jours_min": _clean_int(_cell(row, "jours_min")),
            "jours_max": _clean_int(_cell(row, "jours_max")),
            "cout_jour_estime": _clean_float(_cell(row, "cout_jour_estime")),
            "ordre": ordre,
            "progression": progression or _infer_progression(nom, ordre),
            "priorite": _clean_int(_cell(row, "priorite")) or 3,
            "cout_activite": _clean_float(_cell(row, "cout_activite")),
            "cout_transport_local": _clean_float(_cell(row, "cout_transport_local")),
            "mois_disponibles": _clean_str(_cell(row, "mois_disponibles")),
            "cout_hebergement_jour": _clean_float(_cell(row, "cout_hebergement_jour")),
            "cout_nourriture_jour": _clean_float(_cell(row, "cout_nourriture_jour")),
            "statut": _clean_str(_cell(row, "statut")) or "possible",
            "raison_indisponible": _clean_str(_cell(row, "raison_indisponible")),
        })
    return out


def sync_voyage(session: Session, path: Path) -> dict:
    """Écrase la table cache `lieu_voyage` avec le contenu de l'Excel.

    Retourne `{"lieux": n, "incomplets": [noms]}` — un lieu non visité sans
    aéroport IATA, sans fourchette de jours, ou sans coût/jour estimé n'est
    pas utilisable comme candidat de planification.
    """
    rows = parse_voyage_xlsx(path)
    for old in session.exec(select(LieuVoyage)).all():
        session.delete(old)
    incomplets: list[str] = []
    for r in rows:
        session.add(LieuVoyage(**r))
        if not r["visite"] and (
            not r["aeroport_iata"] or r["jours_min"] is None or r["jours_max"] is None
            or r["cout_jour_estime"] is None
        ):
            incomplets.append(r["nom"])
    session.commit()
    return {"lieux": len(rows), "incomplets": incomplets}


def marquer_visites(session: Session, path: Path, noms: list[str]) -> Path:
    """Marque `noms` comme visités : backup horodaté, écrit `Visité=True`
    dans l'Excel (ligne trouvée par correspondance exacte de `Lieux`), et
    met à jour le cache DB en une seule opération.

    Nécessaire car `sync_voyage` est un import destructif (écrase la table) :
    sans écriture Excel, la prochaine synchro effacerait `visite=True`.
    """
    import datetime as dt
    import shutil

    import openpyxl

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.backup-{ts}{path.suffix}")
    shutil.copy2(path, backup)

    wb = openpyxl.load_workbook(path)  # writable (pas read_only)
    ws = wb.worksheets[0]
    header = {cell.value: cell.column for cell in ws[1]}
    col_lieux = header.get(_COLS["nom"])
    col_visite = header.get(_COLS["visite"])
    if col_lieux is None or col_visite is None:
        raise ValueError(f"Colonnes '{_COLS['nom']}' ou '{_COLS['visite']}' introuvables dans {path}")

    remaining = set(noms)
    for row in range(2, ws.max_row + 1):
        cell_nom = ws.cell(row=row, column=col_lieux).value
        if cell_nom and str(cell_nom).strip() in remaining:
            ws.cell(row=row, column=col_visite, value=True)
            remaining.discard(str(cell_nom).strip())

    if remaining:
        raise ValueError(f"Noms introuvables dans {path}: {', '.join(sorted(remaining))}")

    wb.save(path)

    for lv in session.exec(select(LieuVoyage).where(LieuVoyage.nom.in_(noms))).all():
        lv.visite = True
        session.add(lv)
    session.commit()
    return backup
