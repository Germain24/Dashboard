"""Options du constructeur d'automatisations no-code (#205).

Expose, de façon data-driven, ce que l'UI propose pour composer une routine
« SI <déclencheur> ALORS <actions> » sans écrire de cron ni de JSON :
- les événements métier déclencheurs,
- les automatisations (jobs) lançables en action,
- les types d'action disponibles.
"""

from __future__ import annotations

from app.core.events import Events

# Événements déclencheurs (valeur technique -> libellé lisible).
BUILDER_EVENTS: list[dict[str, str]] = [
    {"value": Events.BUDGET_TRANSACTION_CREATED, "label": "Nouvelle transaction (budget)"},
    {"value": Events.SANTE_WEIGHT_LOGGED, "label": "Poids enregistré (santé)"},
    {"value": Events.ENTRAINEMENT_WORKOUT_LOGGED, "label": "Séance enregistrée (entraînement)"},
    {"value": Events.HABITUDE_CHECKED, "label": "Habitude cochée"},
    {"value": Events.AGENDA_EVENT_CREATED, "label": "Événement agenda créé"},
]

# Automatisations lançables via l'action "job" (sous-ensemble pertinent).
BUILDER_JOBS: list[dict[str, str]] = [
    {"id": "briefing_matin", "label": "Briefing du matin"},
    {"id": "recap_soir", "label": "Récap du soir"},
    {"id": "courses_check", "label": "Vérifier les courses"},
    {"id": "skincare_reorder", "label": "Réapprovisionner skincare"},
    {"id": "budget_rebalancing", "label": "Rééquilibrer le budget"},
    {"id": "portfolio_snapshot", "label": "Snapshot du portefeuille"},
    {"id": "nutrition_plan", "label": "Générer le plan nutrition"},
    {"id": "daily_snapshot", "label": "Snapshot quotidien (journal de vie)"},
]

# Types d'action proposés dans le composeur.
BUILDER_ACTION_TYPES: list[dict[str, str]] = [
    {"type": "notify", "label": "Envoyer une notification"},
    {"type": "job", "label": "Lancer une automatisation"},
]


def builder_options() -> dict[str, list[dict[str, str]]]:
    """Renvoie toutes les options du constructeur no-code."""
    return {
        "events": BUILDER_EVENTS,
        "jobs": BUILDER_JOBS,
        "action_types": BUILDER_ACTION_TYPES,
    }
