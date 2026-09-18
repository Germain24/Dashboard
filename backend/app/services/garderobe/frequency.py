"""Suivi de la fréquence de port (#77).

Exploite le compteur `portes` (incrémenté à chaque /valider). Met en avant :
- les pièces jamais portées (candidates au recyclage),
- les moins portées (rotation faible),
- les plus portées (les chouchous).

Logique pure (`wear_buckets`) testable sans base ; la route mappe les ids vers
des `VetementRead`.
"""

from __future__ import annotations

from typing import Any


def wear_buckets(items: list[dict[str, Any]], top_n: int = 5) -> dict[str, Any]:
    """Catégorise les pièces par fréquence de port.

    Retourne des listes d'ids :
        {never_worn, least_worn, most_worn, total, never_worn_count}
    `least_worn` exclut les jamais portées (qui ont leur propre liste).
    """
    def portes(it: dict) -> int:
        try:
            return int(it.get("portes") or 0)
        except (TypeError, ValueError):
            return 0

    never = [it["id"] for it in items if portes(it) == 0]
    worn = [it for it in items if portes(it) > 0]
    worn_sorted = sorted(worn, key=portes)

    return {
        "total": len(items),
        "never_worn_count": len(never),
        "never_worn": never,
        "least_worn": [it["id"] for it in worn_sorted[:top_n]],
        "most_worn": [it["id"] for it in sorted(worn, key=portes, reverse=True)[:top_n]],
    }
