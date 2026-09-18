"""Tests — options du constructeur no-code (#205)."""

from __future__ import annotations

from app.core.events import Events
from app.services.automatisations.builder import builder_options


def test_builder_options_structure():
    opts = builder_options()
    assert set(opts) == {"events", "jobs", "action_types"}
    # Événements : valeurs alignées sur les constantes canoniques.
    values = {e["value"] for e in opts["events"]}
    assert Events.BUDGET_TRANSACTION_CREATED in values
    assert Events.HABITUDE_CHECKED in values
    assert all("label" in e and "value" in e for e in opts["events"])
    # Jobs et types d'action non vides et bien formés.
    assert opts["jobs"] and all("id" in j and "label" in j for j in opts["jobs"])
    types = {a["type"] for a in opts["action_types"]}
    assert {"notify", "job"} <= types
