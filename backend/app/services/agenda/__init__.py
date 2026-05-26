"""Module Agenda — services métier (CONV 5).

Découpage (chaque sous-module < 200 lignes, cf. PLAN.md note 9) :

- `recurrence`          : expansion pure des règles de répétition hebdo
- `slots`               : détection de créneaux libres dans une journée
- `events`              : CRUD Evenement + CRUD RegleRecurrence + vue combinée
- `tasks`               : CRUD Tache (priorité, deadline, statut)
- `ical_adapter`        : parseur .ics (RFC 5545 V1)
- `entrainement_bridge` : import in-process séance du jour (PLAN.md note 14)

Contrat avec CONV 6 (Études) :
    Créer des tâches via `create_task(session, {..., "source": "etudes", "source_id": devoir_id})`
"""

from app.services.agenda.entrainement_bridge import get_training_block_for_date
from app.services.agenda.events import (
    create_event,
    create_recurrence_rule,
    delete_event,
    delete_recurrence_rule,
    get_event,
    get_full_calendar,
    get_recurrence_rule,
    list_events_for_window,
    list_recurrence_rules,
    update_event,
    update_recurrence_rule,
)
from app.services.agenda.ical_adapter import parse_ics
from app.services.agenda.recurrence import expand_rules_for_window
from app.services.agenda.slots import free_slots
from app.services.agenda.tasks import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    mark_done,
    tasks_due_today,
    update_task,
)

__all__ = [
    "create_event",
    "create_recurrence_rule",
    "create_task",
    "delete_event",
    "delete_recurrence_rule",
    "delete_task",
    "expand_rules_for_window",
    "free_slots",
    "get_event",
    "get_full_calendar",
    "get_recurrence_rule",
    "get_task",
    "get_training_block_for_date",
    "list_events_for_window",
    "list_recurrence_rules",
    "list_tasks",
    "mark_done",
    "parse_ics",
    "tasks_due_today",
    "update_event",
    "update_recurrence_rule",
    "update_task",
]
