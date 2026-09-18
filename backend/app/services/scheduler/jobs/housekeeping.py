"""Job quotidien de placement des corvées domestiques."""

from app.services.agenda.housekeeping import ensure_housekeeping_events


def run(session) -> str:
    result = ensure_housekeeping_events(session)
    return (
        f"Corvées: {len(result['created'])} créée(s), "
        f"{len(result['existing'])} déjà planifiée(s), "
        f"{len(result['unplaced'])} sans créneau"
    )
