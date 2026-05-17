"""Chargement et normalisation du catalogue aliments depuis la DB.

L'aliment a été importé par CONV 1 en transposant le CSV legacy. Chaque
`Aliment.proprietes` est un dict `{nom_colonne: valeur}`. On reconstruit un
DataFrame pandas indexé par nom d'aliment (compatible avec l'optimiseur
legacy).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from app.models.sante import Aliment
from app.services.sante.constants import SUGAR_COMPONENTS

# Colonnes attendues par l'optimiseur — toute colonne manquante est fillée à 0
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


def load_aliments_dataframe(session: Session) -> pd.DataFrame:
    """Charge le catalogue aliments depuis la DB sous forme de DataFrame.

    - Index : nom de l'aliment
    - Colonnes : toutes les propriétés (REQUIRED_COLS + colonnes en surplus)
    - Valeurs : coercées en float, NaN → 0.0
    - Colonne dérivée `TotalSugars` = somme des composants sucrés
    """
    rows = session.exec(select(Aliment)).all()
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLS)

    records = []
    for a in rows:
        rec: dict = {"_nom": a.nom}
        rec.update(a.proprietes or {})
        records.append(rec)

    df = pd.DataFrame.from_records(records).set_index("_nom")
    df.index.name = None

    # Normalisation noms de colonnes (cohérence avec le legacy)
    df.columns = [
        c.replace("AG monoinsaturés", "AG monoinsatures")
         .replace("Énergie", "Energie")
        for c in df.columns
    ]

    # S'assure que toutes les colonnes requises existent et sont numériques
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Pré-calcul TotalSugars (somme des composants sucrés)
    df["TotalSugars"] = df[SUGAR_COMPONENTS].sum(axis=1)

    return df


def aliment_to_dict(a: Aliment) -> dict:
    """Aliment ORM → dict plat (utile pour l'API)."""
    out: dict = {"id": a.id, "nom": a.nom}
    out.update(a.proprietes or {})
    return out


def get_food_names(session: Session) -> list[str]:
    return [a.nom for a in session.exec(select(Aliment).order_by(Aliment.nom)).all()]


def get_aliment_by_name(session: Session, nom: str) -> Optional[Aliment]:
    stmt = select(Aliment).where(Aliment.nom == nom)
    return session.exec(stmt).first()
