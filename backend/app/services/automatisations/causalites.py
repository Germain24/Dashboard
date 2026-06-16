"""Détection de « causalités probables » (#224).

⚠️ On ne prouve PAS de causalité depuis des données d'observation. On détecte
des **liens décalés dans le temps** : une métrique d'un jour J corrèle-t-elle
avec une autre le jour J+lag ? (« nuits courtes aujourd'hui → grignotage demain »).
C'est une PISTE à explorer, pas une preuve — l'UI le dit explicitement.

Réutilise pearson et extract_metrics (#221).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlmodel import Session, select

from app.models.snapshot import DailySnapshot
from app.services.automatisations.correlations import extract_metrics, pearson


def detect_lagged_links(
    series: dict[str, dict[dt.date, float]],
    *,
    lag: int = 1,
    min_pairs: int = 7,
    min_abs_r: float = 0.4,
) -> list[dict[str, Any]]:
    """Liens orientés A(J) -> B(J+lag) par corrélation de Pearson décalée.

    Chaque paire ordonnée (A, B), A≠B, est testée : on apparie A[d] avec
    B[d+lag]. Garde ceux avec ≥ min_pairs points et |r| ≥ min_abs_r, triés par |r|.
    """
    labels = sorted(series)
    results: list[dict[str, Any]] = []
    for a in labels:
        for b in labels:
            if a == b:
                continue
            xs: list[float] = []
            ys: list[float] = []
            for d, va in series[a].items():
                d2 = d + dt.timedelta(days=lag)
                if d2 in series[b]:
                    xs.append(va)
                    ys.append(series[b][d2])
            if len(xs) < min_pairs:
                continue
            r = pearson(xs, ys)
            if r is None or abs(r) < min_abs_r:
                continue
            results.append({
                "cause": a, "effet": b, "lag": lag, "r": round(r, 3), "n": len(xs),
                "piste": f"{a} (jour J) précède {b} (J+{lag})",
            })
    results.sort(key=lambda x: -abs(x["r"]))
    return results


def compute_causalites(
    session: Session, *, days: int = 90, lag: int = 1,
    min_pairs: int = 7, min_abs_r: float = 0.4,
) -> list[dict[str, Any]]:
    """Charge les snapshots récents et en déduit des pistes de liens décalés."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = session.exec(select(DailySnapshot).where(DailySnapshot.date >= cutoff)).all()
    snapshots: list[tuple[dt.date, dict]] = []
    for row in rows:
        try:
            snapshots.append((row.date, json.loads(row.data)))
        except (ValueError, TypeError):
            continue
    series = extract_metrics(snapshots)
    return detect_lagged_links(series, lag=lag, min_pairs=min_pairs, min_abs_r=min_abs_r)
