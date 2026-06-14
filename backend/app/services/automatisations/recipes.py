"""Recettes : chaînes d'actions cross-module lancées à la demande (#215).

Une « recette » enchaîne plusieurs actions (cross-module) en un seul geste, avec
confirmation unique côté UI. Contrairement aux routines, elles ne sont pas
planifiées : on les déclenche manuellement (ex. « Préparer la semaine »).
Réutilise le moteur d'actions (engine.run_action_list) et respecte le kill switch.
"""

from __future__ import annotations

from sqlmodel import Session

from app.services.automatisations.engine import run_action_list
from app.services.settings import get_preferences

RECIPES: list[dict] = [
    {
        "id": "preparer_semaine",
        "name": "Préparer la semaine",
        "emoji": "🗓️",
        "description": "Génère le plan nutrition, vérifie les courses et rééquilibre le budget.",
        "actions": [
            {"type": "job", "job_id": "nutrition_plan"},
            {"type": "job", "job_id": "courses_check"},
            {"type": "job", "job_id": "budget_rebalancing"},
            {"type": "notify", "titre": "🗓️ Semaine préparée",
             "message": "Plan nutrition, courses et budget mis à jour."},
        ],
    },
    {
        "id": "bilan_jour",
        "name": "Bilan du jour",
        "emoji": "🌙",
        "description": "Snapshot quotidien (journal de vie) + récap du soir.",
        "actions": [
            {"type": "job", "job_id": "daily_snapshot"},
            {"type": "job", "job_id": "recap_soir"},
        ],
    },
    {
        "id": "demarrage_journee",
        "name": "Démarrer la journée",
        "emoji": "☀️",
        "description": "Briefing du matin + snapshot du portefeuille.",
        "actions": [
            {"type": "job", "job_id": "briefing_matin"},
            {"type": "job", "job_id": "portfolio_snapshot"},
        ],
    },
]


def get_recipes() -> list[dict]:
    """Recettes disponibles (sans le détail des actions internes)."""
    return [
        {"id": r["id"], "name": r["name"], "emoji": r["emoji"],
         "description": r["description"], "nb_actions": len(r["actions"])}
        for r in RECIPES
    ]


def get_recipe(recipe_id: str) -> dict | None:
    return next((r for r in RECIPES if r["id"] == recipe_id), None)


def run_recipe(session: Session, recipe_id: str) -> str:
    """Exécute une recette (chaîne d'actions). Respecte le kill switch (#217)."""
    recipe = get_recipe(recipe_id)
    if recipe is None:
        raise ValueError(f"Recette {recipe_id!r} introuvable")
    if get_preferences().get("automatisations_kill_switch"):
        return "bloqué (kill switch global actif)"
    _status, detail = run_action_list(session, recipe["actions"], source=f"recipe_{recipe_id}")
    session.commit()
    return detail
