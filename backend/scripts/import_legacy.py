"""Importe les données legacy depuis `data/imports/` vers SQLite.

Idempotent : peut être relancé sans dupliquer les lignes (upsert sur clé naturelle).

Sources attendues dans `data/imports/` :
- `vetements.json`               -> table `vetement`
- `tenues_history.json`          -> table `tenue_history`
- `sante.json`                   -> tables `mesure_sante` + `plan_nutrition`
- `aliments.csv`                 -> table `aliment`
- `Historique_portefeuille.xlsx` -> table `snapshot_portefeuille`
- `ToutBroker.xlsx`              -> table `watchlist_entry`

Usage :
    uv run python scripts/import_legacy.py
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import sys
from pathlib import Path

# Permettre `python scripts/import_legacy.py` depuis backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.models import (  # noqa: E402
    Aliment,
    MesureSante,
    PlanNutrition,
    SnapshotPortefeuille,
    TenueHistory,
    Vetement,
    WatchlistEntry,
)

log = logging.getLogger("import_legacy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

IMPORTS = settings.imports_dir


# ---------- helpers ----------


def _parse_date(value) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    log.warning("Date non parsable: %r", value)
    return None


def _parse_datetime(value) -> dt.datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value
    s = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    log.warning("Datetime non parsable: %r", value)
    return None


def _to_float(v):
    if v in (None, "", "—"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        try:
            return float(str(v).replace(",", ".").replace(" ", ""))
        except ValueError:
            return None


# ---------- importers ----------


def import_vetements(session: Session) -> int:
    path = IMPORTS / "vetements.json"
    if not path.exists():
        log.warning("Pas de fichier %s, skip.", path)
        return 0
    with path.open("r", encoding="utf-8") as f:
        items = json.load(f)
    n = 0
    for it in items:
        existing = session.get(Vetement, it["id"])
        data = {
            "id": it["id"],
            "nom": it.get("nom", ""),
            "marque": it.get("marque"),
            "categorie": it.get("categorie", ""),
            "sous_categorie": it.get("sous_categorie"),
            "matiere": it.get("matiere"),
            "couleur": it.get("couleur"),
            "temp_min": it.get("temp_min"),
            "temp_max": it.get("temp_max"),
            "etat_propre": it.get("etat_propre"),
            "usure_max": it.get("usure_max"),
            "portes": it.get("portes", 0) or 0,
            "impermeable": bool(it.get("impermeable", False)),
            "style": it.get("style"),
        }
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.updated_at = dt.datetime.utcnow()
        else:
            session.add(Vetement(**data))
        n += 1
    session.commit()
    log.info("Vetement : %d lignes upsertées", n)
    return n


def import_tenues(session: Session) -> int:
    path = IMPORTS / "tenues_history.json"
    if not path.exists():
        log.warning("Pas de fichier %s, skip.", path)
        return 0
    with path.open("r", encoding="utf-8") as f:
        items = json.load(f)
    # Clean wipe + re-insert (petit volume, simple)
    for row in session.exec(select(TenueHistory)).all():
        session.delete(row)
    session.commit()

    n = 0
    for it in items:
        d = _parse_datetime(it.get("date"))
        if d is None:
            continue
        session.add(
            TenueHistory(
                date=d,
                tenue=it.get("tenue") or {},
                ids=it.get("ids") or {},
            )
        )
        n += 1
    session.commit()
    log.info("TenueHistory : %d lignes insérées", n)
    return n


def import_sante(session: Session) -> int:
    path = IMPORTS / "sante.json"
    if not path.exists():
        log.warning("Pas de fichier %s, skip.", path)
        return 0
    with path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    n_mesures, n_plans = 0, 0
    for e in entries:
        d = _parse_date(e.get("date"))
        if d is None:
            continue
        # Mesure (poids)
        if "poids" in e and e["poids"] is not None:
            existing = session.exec(select(MesureSante).where(MesureSante.date == d)).first()
            extra = {k: v for k, v in e.items() if k not in {"date", "poids", "targets", "quantites"}}
            if existing:
                existing.poids = e.get("poids")
                existing.extra = extra or None
            else:
                session.add(MesureSante(date=d, poids=e.get("poids"), extra=extra or None))
            n_mesures += 1
        # Plan nutrition
        if "targets" in e and e["targets"]:
            existing_plan = session.exec(
                select(PlanNutrition).where(PlanNutrition.date == d)
            ).first()
            quantites = e.get("quantites")
            extra = {k: v for k, v in e.items() if k not in {"date", "poids", "targets", "quantites"}}
            if existing_plan:
                existing_plan.targets = e["targets"]
                existing_plan.quantites = quantites
                existing_plan.extra = extra or None
            else:
                session.add(
                    PlanNutrition(
                        date=d,
                        targets=e["targets"],
                        quantites=quantites,
                        extra=extra or None,
                    )
                )
            n_plans += 1
    session.commit()
    log.info("MesureSante : %d / PlanNutrition : %d", n_mesures, n_plans)
    return n_mesures + n_plans


def import_aliments(session: Session) -> int:
    """Aliments.csv legacy : 1 ligne = 1 propriété, colonnes = aliments.

    On transpose : 1 ligne = 1 aliment, sa colonne de propriétés en dict.
    Séparateur : `;`.
    """
    path = IMPORTS / "aliments.csv"
    if not path.exists():
        log.warning("Pas de fichier %s, skip.", path)
        return 0

    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    if not rows:
        return 0

    header = rows[0]  # ['Nutriments', aliment1, aliment2, ...]
    aliments = header[1:]
    properties: dict[str, dict[str, float | None]] = {a: {} for a in aliments}
    for row in rows[1:]:
        if not row:
            continue
        prop_name = row[0]
        for i, a in enumerate(aliments, start=1):
            if i < len(row):
                properties[a][prop_name] = _to_float(row[i])

    # Wipe + re-insert
    for r in session.exec(select(Aliment)).all():
        session.delete(r)
    session.commit()

    n = 0
    for nom, props in properties.items():
        if not nom:
            continue
        session.add(Aliment(nom=nom, proprietes=props))
        n += 1
    session.commit()
    log.info("Aliment : %d lignes insérées", n)
    return n


def import_portefeuille(session: Session) -> int:
    path = IMPORTS / "Historique_portefeuille.xlsx"
    if not path.exists():
        log.warning("Pas de fichier %s, skip.", path)
        return 0
    try:
        from python_calamine import CalamineWorkbook
    except ImportError:  # pragma: no cover
        log.error("python-calamine non installé.")
        return 0

    wb = CalamineWorkbook.from_path(str(path))
    ws = wb.get_sheet_by_index(0)
    data = ws.to_python()
    if not data:
        return 0
    header = [str(h).strip().lower() for h in data[0]]
    try:
        i_date = header.index("date")
        i_val = header.index("valeur")
        i_inv = header.index("investit")
    except ValueError:
        log.error("Colonnes attendues 'Date|Valeur|Investit' manquantes. Header: %s", header)
        return 0

    n = 0
    for row in data[1:]:
        d = _parse_date(row[i_date])
        if d is None:
            continue
        val = _to_float(row[i_val])
        inv = _to_float(row[i_inv])
        if val is None or inv is None:
            continue
        existing = session.exec(
            select(SnapshotPortefeuille).where(SnapshotPortefeuille.date == d)
        ).first()
        if existing:
            existing.valeur = val
            existing.investit = inv
        else:
            session.add(SnapshotPortefeuille(date=d, valeur=val, investit=inv))
        n += 1
    session.commit()
    log.info("SnapshotPortefeuille : %d lignes upsertées", n)
    return n


def import_watchlist(session: Session) -> int:
    path = IMPORTS / "ToutBroker.xlsx"
    if not path.exists():
        log.warning("Pas de fichier %s, skip.", path)
        return 0
    try:
        from python_calamine import CalamineWorkbook
    except ImportError:  # pragma: no cover
        return 0

    wb = CalamineWorkbook.from_path(str(path))
    ws = wb.get_sheet_by_index(0)
    data = ws.to_python()
    if not data:
        return 0

    # Header attendu (depuis l'analyse) :
    # Ticker | Nom | Pays | Secteur | Prix | EPS | PER | Croissance | PEG | Volume
    # Achat | Chance MOAT | Poids | Tradding 212 | Bourse Direct | Bourse Direct 2 | IBKR
    # Secteur 1..5
    H = [str(h).strip() for h in data[0]]

    def col(name: str) -> int | None:
        try:
            return H.index(name)
        except ValueError:
            return None

    i_tic = col("Ticker Yahoo Finance") or col("Ticker") or 0
    i_nom = col("Nom")
    i_pays = col("Pays")
    i_sect = col("Secteur")
    i_prix = col("Prix")
    i_eps = col("EPS")
    i_per = col("PER")
    i_cr = col("Croissance")
    i_peg = col("PEG")
    i_vol = col("Volume")
    i_ach = col("Achat")
    i_moat = col("Chance MOAT")
    i_poids = col("Poids")
    i_t212 = col("Tradding 212") or col("Trading 212")
    i_bd1 = col("Bourse Direct")
    i_bd2 = col("Bourse Direct 2")
    i_ibkr = col("IBKR")
    s_cols = [col(f"Secteur {k}") for k in range(1, 6)]

    n = 0
    for row in data[1:]:
        ticker = str(row[i_tic]).strip() if i_tic is not None and row[i_tic] else None
        if not ticker:
            continue
        def g(i):
            return row[i] if i is not None and i < len(row) else None

        secteurs_extra = {}
        for k, ci in enumerate(s_cols, start=1):
            v = g(ci)
            if v not in (None, "", 0):
                secteurs_extra[f"secteur_{k}"] = v

        data_row = {
            "ticker": ticker,
            "nom": str(g(i_nom)) if g(i_nom) else None,
            "pays": str(g(i_pays)) if g(i_pays) else None,
            "secteur": str(g(i_sect)) if g(i_sect) else None,
            "prix": _to_float(g(i_prix)),
            "eps": _to_float(g(i_eps)),
            "per": _to_float(g(i_per)),
            "croissance": _to_float(g(i_cr)),
            "peg": _to_float(g(i_peg)),
            "volume": _to_float(g(i_vol)),
            "achat": bool(g(i_ach)) if g(i_ach) is not None else False,
            "chance_moat": _to_float(g(i_moat)),
            "poids": _to_float(g(i_poids)),
            "trading_212": _to_float(g(i_t212)),
            "bourse_direct": _to_float(g(i_bd1)),
            "bourse_direct_2": _to_float(g(i_bd2)),
            "ibkr": _to_float(g(i_ibkr)),
            "secteurs_extra": secteurs_extra or None,
        }

        existing = session.exec(
            select(WatchlistEntry).where(WatchlistEntry.ticker == ticker)
        ).first()
        if existing:
            for k, v in data_row.items():
                setattr(existing, k, v)
            existing.updated_at = dt.datetime.utcnow()
        else:
            session.add(WatchlistEntry(**data_row))
        n += 1
        if n % 500 == 0:
            session.commit()
    session.commit()
    log.info("WatchlistEntry : %d lignes upsertées", n)
    return n


# ---------- main ----------


def main() -> None:
    log.info("Imports depuis : %s", IMPORTS)
    if not IMPORTS.exists():
        log.error("Dossier %s introuvable.", IMPORTS)
        sys.exit(1)

    with Session(engine) as session:
        total = 0
        total += import_vetements(session)
        total += import_tenues(session)
        total += import_sante(session)
        total += import_aliments(session)
        total += import_portefeuille(session)
        total += import_watchlist(session)
    log.info("Total : %d lignes traitées.", total)


if __name__ == "__main__":
    main()
