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
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.config import settings
from app.services.sante.constants import SUGAR_COMPONENTS
from app.services.sante.reservoir import optimizer_product_is_eligible
from app.services.sante.reservoir_overrides import ciqual_override_code

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


def _reservoir_path() -> Path:
    return settings.imports_dir / "Sante" / "tableur" / "reservoir_superc.csv"


@lru_cache(maxsize=16)
def _ciqual_profile(code: str) -> dict[str, float]:
    """Profil nutritionnel CIQUAL par code, utilisé par les redirections sûres."""
    path = settings.imports_dir / "Sante" / "ciqual" / "ciqual_normalise.csv"
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                if str(row.get("CiqualCode") or "").strip() != str(code):
                    continue
                return {
                    key: _to_float(value)
                    for key, value in row.items()
                    if key not in {
                        "CiqualCode", "CiqualNom", "CiqualGroupe", "CiqualSousGroupe",
                    }
                }
    except Exception:
        pass
    return {}


def load_reservoir_from_csv(
    csv_path: Optional[Path] = None,
) -> dict[str, dict[str, float]]:
    """Lit le réservoir généré (`reservoir_superc.csv`), ou {} s'il est absent.

    Format DROIT (une ligne = un aliment), contrairement à `aliments.csv` qui
    est transposé : le réservoir compte des milliers d'aliments, une colonne par
    aliment donnerait un fichier illisible et impossible à ouvrir en tableur.

    Best-effort : un réservoir absent, tronqué ou illisible ne doit jamais
    empêcher de charger le catalogue curé, qui reste la source de vérité.
    """
    path = Path(csv_path) if csv_path is not None else _reservoir_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
    except Exception:
        return {}

    out: dict[str, dict[str, float]] = {}
    for row in rows:
        nom = (row.get("Aliment") or "").strip()
        if not nom:
            continue
        if not optimizer_product_is_eligible(row):
            continue
        override_code = ciqual_override_code(nom)
        # Le seuil historique de construction (0,35) laissait passer des
        # rapprochements manifestement faux : pâtes aux œufs -> pâte de fruits,
        # porc à l'érable -> sirop d'érable, etc. Le réservoir est automatique :
        # à l'exécution on ne garde que les profils suffisamment sûrs.
        try:
            confiance = float(row.get("Confiance") or 0.0)
        except (TypeError, ValueError):
            confiance = 0.0
        if confiance < 0.75 and not override_code:
            continue
        # `Source`, `UPC`, `Rayon`, `CiqualNom` sont du texte de traçabilité :
        # `_to_float` les ramènerait à 0.0 et polluerait le DataFrame de
        # colonnes numériques vides. On ne garde que les teneurs.
        props = {
            key: _to_float(value)
            for key, value in row.items()
            if key and key not in ("Aliment", "Source", "UPC", "Rayon",
                                   "CiqualCode", "CiqualNom")
        }
        if override_code:
            profile = _ciqual_profile(override_code)
            if not profile:
                continue
            # Prix et bornes viennent toujours du produit Super C; seules les
            # teneurs nutritionnelles erronées sont remplacées par CIQUAL.
            preserved = {
                key: props[key] for key in ("Prix", "MinQty", "MaxQty", "Congelable", "CreamiOk")
                if key in props
            }
            props.update(profile)
            props.update(preserved)
        out[nom] = props
    return out


def load_reservoir_product_refs(
    csv_path: Optional[Path] = None,
) -> dict[str, str]:
    """Retourne ``{aliment: UPC Super C}`` depuis le réservoir.

    Le nom d'un produit du réservoir est déjà celui du produit Super C qui a
    servi au rattachement CIQUAL. Conserver son UPC évite de refaire ensuite un
    matching approximatif par mots-clés (et donc de remplir le panier avec un
    autre aliment).
    """
    path = Path(csv_path) if csv_path is not None else _reservoir_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = csv.DictReader(f, delimiter=";")
            refs: dict[str, str] = {}
            for row in rows:
                try:
                    confiance = float(row.get("Confiance") or 0.0)
                except (TypeError, ValueError):
                    confiance = 0.0
                name = (row.get("Aliment") or "").strip()
                upc = (row.get("UPC") or "").strip()
                if name and upc and (
                    confiance >= 0.75 or ciqual_override_code(name)
                ):
                    refs[name] = upc
            return refs
    except Exception:
        return {}


def load_reservoir_ciqual_refs(
    csv_path: Optional[Path] = None,
) -> dict[str, str]:
    """Retourne le profil CIQUAL effectif de chaque produit fiable/redirigé."""
    path = Path(csv_path) if csv_path is not None else _reservoir_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            refs: dict[str, str] = {}
            for row in csv.DictReader(handle, delimiter=";"):
                name = (row.get("Aliment") or "").strip()
                try:
                    confiance = float(row.get("Confiance") or 0.0)
                except (TypeError, ValueError):
                    confiance = 0.0
                override = ciqual_override_code(name)
                code = override or (row.get("CiqualCode") or "").strip()
                if name and code and (override or confiance >= 0.75):
                    refs[name] = code
            return refs
    except Exception:
        return {}


def load_aliments_dataframe(
    session=None, *, csv_path: Optional[Path] = None, include_reservoir: bool = False,
) -> pd.DataFrame:
    """Charge le catalogue depuis le CSV sous forme de DataFrame.

    `session` est ignoré (gardé pour compat des appelants existants).
    `csv_path` permet de pointer un fichier alternatif (utile en test).
    `include_reservoir` concatène le réservoir Super C généré
    (`reservoir_superc.csv`) DERRIÈRE le catalogue curé. Défaut `False` : les
    appelants et les tests existants ne voient aucun changement ; seule la
    génération de fenêtre l'active.

    En cas d'homonymie, l'entrée CURÉE gagne toujours : elle a été vérifiée à la
    main, l'autre est le fruit d'un rattachement automatique.

    - Index : nom de l'aliment
    - Colonnes : toutes les propriétés (REQUIRED_COLS + colonnes en surplus)
    - Valeurs : coercées en float, NaN → 0.0
    - Colonne dérivée `TotalSugars` = somme des composants sucrés
    """
    properties = load_aliments_from_csv(csv_path)
    # Complément de produits complets courants, profils CIQUAL et prix toujours
    # vérifiés ensuite contre Super C. Le tableur curé reste prioritaire.
    if csv_path is None:
        try:
            from app.services.sante.common_foods import load_common_foods

            properties = {**load_common_foods(), **properties}
        except Exception:
            pass
        # CIQUAL ne publie pas de profil distinct pour le yogourt grec de lait
        # de vache à 2 %, alors que c'est la variante nature la plus courante
        # chez Super C au Québec. On la dérive du profil curé 0 % : mêmes
        # protéines/micros, +2 g de lipides et +18 kcal par 100 g. Son prix
        # reste nul ici et doit être résolu depuis Super C.
        base = properties.get("Yogourt grec nature 0%")
        if base and "Yogourt grec nature 2%" not in properties:
            greek_2 = base.copy()
            greek_2.update({
                "Prix": 0.0,
                "Lipides": 2.0,
                "Energie": float(base.get("Energie", 0.0)) + 18.0,
                "MinQty": 0.0,
                "MaxQty": 400.0,
            })
            properties["Yogourt grec nature 2%"] = greek_2
    if include_reservoir:
        reservoir = load_reservoir_from_csv()
        # `properties` en second : ses clés écrasent celles du réservoir.
        properties = {**reservoir, **properties}
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
