"""Garde-fous de l'agent (#163).

- Les outils de MUTATION exigent une confirmation explicite avant exécution.
- Toute action est journalisée (table RobotAction) — fait côté agent/route.
"""

from __future__ import annotations

from app.services.robot.tools import is_mutation


def requires_confirmation(tool_name: str) -> bool:
    """True si l'outil modifie des données et doit être confirmé avant exécution."""
    return is_mutation(tool_name)


def action_status(tool_name: str, confirmed: bool) -> str:
    """Statut à enregistrer pour une action.

    - lecture seule -> "auto"
    - mutation confirmée -> "executed"
    - mutation non confirmée -> "pending"
    """
    if not requires_confirmation(tool_name):
        return "auto"
    return "executed" if confirmed else "pending"
