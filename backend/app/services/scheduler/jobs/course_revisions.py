"""Job hebdomadaire de révision des cours, avec Shopify comme lieu préféré."""

from __future__ import annotations


def run(session) -> str:
    from app.services.agenda.weekly_revisions import run_weekly_revisions

    return run_weekly_revisions(session)
