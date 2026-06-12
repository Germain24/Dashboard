"""Modèles de routines prêts à l'emploi (#206)."""

from __future__ import annotations

ROUTINE_TEMPLATES = [
    {
        "id": "semaine_type",
        "name": "Semaine type",
        "description": "Briefing matin lun-ven à 7h + récap soir à 21h.",
        "trigger_type": "cron",
        "trigger_value": "0 7 * * 1-5",
        "actions": [{"type": "job", "job_id": "briefing_matin"}],
    },
    {
        "id": "jour_sport",
        "name": "Jour sport",
        "description": "Notification de motivation avant chaque séance (lun/mer/ven 8h).",
        "trigger_type": "cron",
        "trigger_value": "0 8 * * 1,3,5",
        "actions": [
            {"type": "notify", "titre": "💪 Jour de sport !", "message": "C'est l'heure de t'entraîner. Lance ta séance."}
        ],
    },
    {
        "id": "mode_weekend",
        "name": "Mode week-end",
        "description": "Récap détendu le samedi et dimanche matin à 9h.",
        "trigger_type": "cron",
        "trigger_value": "0 9 * * 6,0",
        "actions": [{"type": "job", "job_id": "briefing_matin"}],
    },
]


def get_templates() -> list[dict]:
    return ROUTINE_TEMPLATES


def get_template(template_id: str) -> dict | None:
    return next((t for t in ROUTINE_TEMPLATES if t["id"] == template_id), None)
