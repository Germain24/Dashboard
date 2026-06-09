"""Chargement du catalogue aliments DEPUIS LE CSV (data/imports/aliments.csv).

Choix de design (décidé après CONV 3 sur retour utilisateur) : le CSV est la
**source de vérité** pour le catalogue. À chaque appel de l'optimiseur, on
relit le CSV. Comme ça l'utilisateur édite `aliments.csv` à la main (ajout,
suppression, ajustement d'un prix ou d'une teneur) et au prochain "Générer le
plan" les modifications sont prises en compte — sans réimport manuel.

La table SQL `aliment` (créée par CONV 1) n'est plus consultée par la logique
nutrition. Elle est conservée pour ne pas casser de migration ; à terme, on
pourra la supprimer.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.config import settings
from app.services.sante.constants import SUGAR_COMPONENTS

REQUIRED_COLS: list[str] = [
    "Prix", "Proteines", "Lipides", "Glucides", "Energie", "Fibres",
    "AG satures", "AG monoinsatures", "Omega 3", "Omega 6",
    *SUGAR_COMPONENTS,
    "Sodium", "Magnesium", "VitA", "VitB1", "VitB2", "VitB3", "VitB5",
    "VitB6", "VitB9", "VitB12", "VitC", "VitD", "VitE", "VitK",
    "Calcium", "Chlorure", "Cuivre", "Fer", "Iode", "Manganese",
    "Phosphore", "Potassium", "Selenium", "Zinc", "Cholesterol",
    "Polyols", "MinQty", "MaxQty",
]


def _resolve_csv_path(csv_path: Optional[Path] = None) -> Path:
    """Retourne le chemin du CSV à utiliser (override paramètre > settings)."""
    if csv_path is not None:
        return Path(csv_path)
    # Rangé sous data/imports/Sante/tableur/ (cf. #6).
    return settings.imports_dir / "Sante" / "tableur" / "aliments.csv"


def _to_float(s: str) -> float:
    """Parse une valeur CSV en float ; valeurs vides ou non numériques → 0.0."""
    if s is None:
        return 0.0
    s = str(s).strip()
    if not s:
        return 0.0
    # Le CSV legacy utilise parfois la virgule comme séparateur décimal
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_aliments_from_csv(csv_path: Optional[Path] = None) -> dict[str, dict[str, float]]:
    """Lit `aliments.csv` (1 ligne = 1 propriété, colonnes = aliments) et
    retourne `{aliment: {propriete: valeur}}`.

    Tolère utf-8-sig (BOM) et séparateur `;`. Les valeurs vides → 0.0.
    """
    path = _resolve_csv_path(csv_path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    if not rows:
        return {}

    header = rows[0]
    aliments = [a for a in header[1:] if a and a.strip()]
    out: dict[str, dict[str, float]] = {a: {} for a in aliments}

    for row in rows[1:]:
        if not row:
            continue
        prop_name = (row[0] or "").strip()
        if not prop_name:
            continue
        for i, a in enumerate(aliments, start=1):
            if i < len(row):
                out[a][prop_name] = _to_float(row[i])
    return out


def load_aliments_dataframe(session=None, *, csv_path: Optional[Path] = None) -> pd.DataFrame:
    """Charge le catalogue depuis le CSV sous forme de DataFrame.

    `session` est ignoré (gardé pour compat des appelants existants).
    `csv_path` permet de pointer un fichier alternatif (utile en test).

    - Index : nom de l'aliment
    - Colonnes : toutes les propriétés (REQUIRED_COLS + colonnes en surplus)
    - Valeurs : coercées en float, NaN → 0.0
    - Colonne dérivée `TotalSugars` = somme des composants sucrés
    """
    properties = load_aliments_from_csv(csv_path)
    if not properties:
        return pd.DataFrame(columns=REQUIRED_COLS)

    records = []
    for nom, props in properties.items():
        rec: dict = {"_nom": nom}
        rec.update(props)
        records.append(rec)

    df = pd.DataFrame.from_records(records).set_index("_nom")
    df.index.name = None

    # Normalisation des noms de colonnes
    df.columns = [
        c.replace("AG monoinsaturés", "AG monoinsatures")
         .replace("Énergie", "Energie")
        for c in df.columns
    ]

    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["TotalSugars"] = df[SUGAR_COMPONENTS].sum(axis=1)
    return df


def aliment_names(csv_path: Optional[Path] = None) -> list[str]:
    """Liste des noms d'aliments présents dans le CSV (triée)."""
    return sorted(load_aliments_from_csv(csv_path).keys())
