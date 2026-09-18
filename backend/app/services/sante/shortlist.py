"""Présélection des aliments soumis à l'optimiseur.

Le réservoir Super C porte des centaines d'aliments (des milliers une fois tous
les rayons parcourus). SLSQP ne peut pas les absorber : il dérive par
différences finies, donc l'objectif est évalué ~(n+1) fois par itération.
Mesuré sur cette machine, un balayage complet coûte 18 s à 116 aliments et 65 s
à 464 — la croissance est très supérieure au linéaire.

Ce module choisit donc, avant SLSQP, les ~400 candidats les plus prometteurs.
C'est un filtre purement VECTORIEL (aucune optimisation), donc négligeable
devant le solveur.

Trois règles, dans cet ordre :

1. **Rien de ce qui compte n'est jamais évincé** : les aliments curés à la main,
   le contenu du garde-manger et les favoris passent toujours.
2. **Un porteur par nutriment** : pour chaque nutriment ciblé, les meilleurs
   aliments en teneur par dollar sont retenus d'office. Sans cette règle, un tri
   sur un score global écarterait les rares porteurs d'iode, de sélénium ou de
   vitamine D — chers, mal notés en moyenne, et pourtant irremplaçables.
3. **Le reste au score global**, jusqu'au plafond.

Logique PURE et déterministe : mêmes entrées, même sortie.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.services.sante.constants import NUTRIENT_KEY_TO_CSV, TRACKED_MAX_NUTRIENTS

logger = logging.getLogger(__name__)

#: Plafond d'aliments soumis à l'optimiseur (choix user 2026-08-11 : « plus
#: riche » plutôt que « plus rapide »).
DEFAULT_N_MAX = 400

#: Nombre d'aliments retenus d'office par nutriment ciblé (règle 2).
TOP_PAR_NUTRIMENT = 4

#: Nutriments à NE PAS maximiser : sodium, cholestérol, sucres, gras saturés
#: sont des PLAFONDS. Les inclure dans le score reviendrait à présélectionner
#: les aliments les plus salés et les plus sucrés par dollar.
_MAX_CSV_COLS: frozenset[str] = frozenset(
    NUTRIENT_KEY_TO_CSV[k] for k in TRACKED_MAX_NUTRIENTS if k in NUTRIENT_KEY_TO_CSV
)

#: Prix plancher (CAD/100 g) pour la division. Un aliment à prix nul ou négatif
#: (donnée manquante) obtiendrait sinon une densité infinie et raflerait toutes
#: les places.
_PRIX_PLANCHER = 0.01


def _colonnes_ciblees(df: pd.DataFrame, targets: dict[str, float]) -> list[str]:
    """Colonnes du catalogue correspondant aux cibles à COUVRIR (plafonds exclus)."""
    colonnes: list[str] = []
    for key, value in targets.items():
        col = NUTRIENT_KEY_TO_CSV.get(key)
        if col is None or col in _MAX_CSV_COLS or col in colonnes:
            continue
        if col not in df.columns:
            continue
        try:
            if float(value) <= 0.0:
                continue
        except (TypeError, ValueError):
            continue
        colonnes.append(col)
    return colonnes


def build_shortlist(
    df: pd.DataFrame,
    targets: dict[str, float],
    *,
    n_max: int = DEFAULT_N_MAX,
    keep_names: frozenset[str] = frozenset(),
    top_par_nutriment: int = TOP_PAR_NUTRIMENT,
) -> pd.DataFrame:
    """Sous-ensemble d'au plus `n_max` aliments, dans l'ordre du catalogue.

    `keep_names` : aliments à conserver quoi qu'il arrive (curés, garde-manger,
    favoris). S'ils dépassent déjà `n_max`, ils sont TOUS gardés : mieux vaut une
    optimisation lente qu'un plan amputé de ce que l'utilisateur possède déjà.
    """
    if len(df) <= n_max:
        return df

    colonnes = _colonnes_ciblees(df, targets)
    if not colonnes:
        # Sans cible exploitable, aucun critère de tri ne serait défendable :
        # on tronque dans l'ordre du catalogue plutôt que d'inventer un ordre.
        logger.warning("[shortlist] aucune colonne ciblée — troncature simple à %d", n_max)
        garder = [n for n in df.index if n in keep_names]
        autres = [n for n in df.index if n not in keep_names]
        return df.loc[garder + autres[: max(0, n_max - len(garder))]]

    prix = pd.to_numeric(df["Prix"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    prix = np.maximum(prix, _PRIX_PLANCHER)

    teneurs = df[colonnes].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    densites = teneurs / prix[:, None]

    # Normalisation par le MAXIMUM de chaque colonne : sans elle, les nutriments
    # exprimés en µg (iode, sélénium, B12) écraseraient par leur seule échelle
    # ceux exprimés en g, et le score ne refléterait que les unités.
    maxima = densites.max(axis=0)
    maxima[maxima <= 0.0] = 1.0
    normalisees = densites / maxima
    scores = normalisees.sum(axis=1)

    noms = list(df.index)
    retenus: set[str] = {n for n in noms if n in keep_names}

    # Règle 2 : les meilleurs porteurs de CHAQUE nutriment, avant tout tri global.
    for j in range(normalisees.shape[1]):
        colonne = normalisees[:, j]
        if not np.any(colonne > 0.0):
            continue
        meilleurs = np.argsort(-colonne)[:top_par_nutriment]
        for i in meilleurs:
            if colonne[i] > 0.0:
                retenus.add(noms[i])

    # Règle 3 : complétion par score global décroissant.
    if len(retenus) < n_max:
        for i in np.argsort(-scores):
            if len(retenus) >= n_max:
                break
            retenus.add(noms[i])

    # Ordre du catalogue conservé : la sortie de l'optimiseur reste comparable
    # d'une génération à l'autre.
    return df.loc[[n for n in noms if n in retenus]]
