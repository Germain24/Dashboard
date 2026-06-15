"""Moteur de corrélations cross-modules (#221).

À partir des journaux de vie quotidiens (DailySnapshot, #212), aligne les
métriques numériques de différents modules par date et calcule leurs
corrélations de Pearson. Sert à repérer des liens (« moins je dors, plus je
dépense ») — sans prétendre à la causalité.

Fonctions pures (pearson / correlate_series / extract_metrics) -> testables ;
`compute_correlations` charge depuis la base et habille le résultat.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from itertools import combinations
from typing import Any

from sqlmodel import Session, select

from app.models.snapshot import DailySnapshot

# Label lisible -> chemin (section, clé) dans le blob `data` du snapshot.
METRIC_PATHS: dict[str, tuple[str, str]] = {
    "Humeur": ("humeur", "valeur"),
    "Énergie": ("humeur", "energie"),
    "Poids": ("sante", "poids"),
    "Calories": ("sante", "calories"),
    "Dépenses": ("budget", "depenses_total"),
    "Habitudes %": ("habitudes", "pct"),
    "Séances": ("entrainement", "nb_seances"),
    "Tonnage": ("entrainement", "tonnage_kg"),
    "Événements": ("agenda", "nb_evenements"),
}


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Coefficient de corrélation de Pearson. None si variance nulle / trop court."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    r = cov / math.sqrt(vx * vy)
    return max(-1.0, min(1.0, r))


def extract_metrics(
    snapshots: list[tuple[dt.date, dict[str, Any]]],
) -> dict[str, dict[dt.date, float]]:
    """De [(date, data_blob)] -> {label: {date: valeur numérique}}.

    Ignore les valeurs absentes, nulles ou non numériques.
    """
    out: dict[str, dict[dt.date, float]] = {label: {} for label in METRIC_PATHS}
    for date, data in snapshots:
        for label, (section, key) in METRIC_PATHS.items():
            val = (data.get(section) or {}).get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[label][date] = float(val)
    return {k: v for k, v in out.items() if v}


def correlate_series(
    series: dict[str, dict[dt.date, float]],
    *,
    min_pairs: int = 7,
    min_abs_r: float = 0.3,
) -> list[dict[str, Any]]:
    """Corrèle chaque paire de métriques sur leurs dates communes.

    Garde les paires avec ≥ min_pairs points alignés et |r| ≥ min_abs_r.
    Retour trié par |r| décroissant.
    """
    results: list[dict[str, Any]] = []
    for a, b in combinations(sorted(series), 2):
        common = sorted(set(series[a]) & set(series[b]))
        if len(common) < min_pairs:
            continue
        r = pearson([series[a][d] for d in common], [series[b][d] for d in common])
        if r is None or abs(r) < min_abs_r:
            continue
        results.append({"a": a, "b": b, "r": round(r, 3), "n": len(common)})
    results.sort(key=lambda x: -abs(x["r"]))
    return results


def _interpret(r: float) -> str:
    sens = "varient ensemble" if r > 0 else "varient en sens inverse"
    force = "forte" if abs(r) >= 0.7 else "modérée" if abs(r) >= 0.5 else "faible"
    return f"corrélation {force}, {sens}"


def compute_correlations(
    session: Session, *, days: int = 60, min_pairs: int = 7, min_abs_r: float = 0.3,
) -> list[dict[str, Any]]:
    """Charge les snapshots récents, en extrait les métriques et les corrèle."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = session.exec(
        select(DailySnapshot).where(DailySnapshot.date >= cutoff)
    ).all()
    snapshots: list[tuple[dt.date, dict]] = []
    for row in rows:
        try:
            snapshots.append((row.date, json.loads(row.data)))
        except (ValueError, TypeError):
            continue
    metrics = extract_metrics(snapshots)
    correlations = correlate_series(metrics, min_pairs=min_pairs, min_abs_r=min_abs_r)
    for c in correlations:
        c["interpretation"] = _interpret(c["r"])
    return correlations
