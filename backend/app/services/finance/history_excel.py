"""Synchronisation de l'historique de portefeuille avec un fichier Excel.

`data/imports/Historique_portefeuille.xlsx` (colonnes **Date** JJ/MM/AAAA,
**Valeur**, **Investit**) est la **source éditable** des valeurs historiques :

- lu au démarrage de l'app et à la demande → alimente la table
  ``snapshot_portefeuille`` (la courbe du Suivi) ;
- mis à jour quand un nouveau snapshot est pris (la journée s'y ajoute).

Tu édites le fichier → tu relances (ou clique « Recharger l'Excel ») → le
graphique reflète tes valeurs.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Optional

from sqlmodel import Session, select

from app.models.finance import SnapshotPortefeuille

from app.core.config import settings as _settings

# Rangé sous data/imports/Finances/tableur/ (cf. #6).
_REL = os.path.join("data", "imports", "Finances", "tableur", "Historique_portefeuille.xlsx")
_CANDIDATES = [
    str(_settings.imports_dir / "Finances" / "tableur" / "Historique_portefeuille.xlsx"),
    _REL,
    os.path.join("..", _REL),
]


def find_history_file(must_exist: bool = True) -> Optional[str]:
    for c in _CANDIDATES:
        if os.path.exists(c):
            return c
    return None if must_exist else _CANDIDATES[0]


def _parse_date(v) -> Optional[dt.date]:
    import pandas as pd
    try:
        if isinstance(v, dt.datetime):
            return v.date()
        if isinstance(v, dt.date):
            return v
        d = pd.to_datetime(str(v), dayfirst=True, errors="coerce")
        return None if pd.isna(d) else d.date()
    except Exception:
        return None


def _to_float(v) -> Optional[float]:
    """Parse un nombre tolérant au format français : tout type d'espace comme
    séparateur de milliers (espace normal, insécable, fin) et virgule décimale.
    Ex : '27 785,03', '27 785.03', '21 051,60' -> float."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        pass
    s = "".join(ch for ch in str(v).strip() if not ch.isspace())
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def read_history_rows() -> list[tuple[dt.date, float, float]]:
    """Lit (date, valeur, investit) depuis l'Excel. Tolérant sur les noms de
    colonnes, les formats de nombres, et dédoublonne par date (dernière gagne)."""
    path = find_history_file()
    if not path:
        return []
    try:
        import pandas as pd
        df = pd.read_excel(path)
        cols = {str(c).strip().lower(): c for c in df.columns}
        c_date = cols.get("date")
        c_val = cols.get("valeur") or cols.get("value")
        c_inv = cols.get("investit") or cols.get("investi") or cols.get("invested")
        if not c_date or not c_val:
            return []
        rows: list[tuple[dt.date, float, float]] = []
        for _, r in df.iterrows():
            d = _parse_date(r[c_date])
            if d is None:
                continue
            val = _to_float(r[c_val])
            if val is None:
                continue
            inv = _to_float(r[c_inv]) if c_inv is not None else 0.0
            rows.append((d, val, inv if inv is not None else 0.0))
        # dédoublonnage par date (dernière occurrence gagne), tri chronologique
        dedup = {d: (v, i) for d, v, i in rows}
        return sorted(((d, v, i) for d, (v, i) in dedup.items()), key=lambda t: t[0])
    except Exception as e:
        print(f"[history_excel] lecture: {e}")
        return []


def sync_excel_to_db(session: Session) -> int:
    """Importe l'Excel dans snapshot_portefeuille (insère/met à jour). Un seul
    commit ; seules les lignes nouvelles ou modifiées sont touchées."""
    rows = read_history_rows()
    if not rows:
        return 0
    existing = {s.date: s for s in session.exec(select(SnapshotPortefeuille)).all()}
    changed = 0
    for d, val, inv in rows:
        s = existing.get(d)
        if s is None:
            session.add(SnapshotPortefeuille(date=d, valeur=val, investit=inv))
            changed += 1
        elif abs((s.valeur or 0) - val) > 1e-6 or abs((s.investit or 0) - inv) > 1e-6:
            s.valeur = val
            s.investit = inv
            session.add(s)
            changed += 1
    if changed:
        session.commit()
        print(f"[history_excel] {changed} snapshots synchronises depuis l'Excel")
    return changed


def write_snapshot_to_excel(date: dt.date, valeur: float, investit: float) -> bool:
    """Insère/met à jour une ligne dans l'Excel (source éditable). Best-effort :
    si le fichier est ouvert/verrouillé, on n'échoue pas (le snapshot reste en DB)."""
    path = find_history_file(must_exist=False)
    if not path:
        return False
    try:
        import pandas as pd
        rows: dict[dt.date, tuple[float, float]] = {}
        if os.path.exists(path):
            for d, v, i in read_history_rows():
                rows[d] = (v, i)
        rows[date] = (float(valeur), float(investit))
        ordered = sorted(rows.items(), key=lambda kv: kv[0])
        df = pd.DataFrame([
            {"Date": d.strftime("%d/%m/%Y"), "Valeur": round(v, 2), "Investit": round(i, 2)}
            for d, (v, i) in ordered
        ])
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        df.to_excel(path, index=False)
        return True
    except Exception as e:
        print(f"[history_excel] ecriture (fichier ouvert ?) : {e}")
        return False
