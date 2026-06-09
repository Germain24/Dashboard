"""Import d'événements iCal (fichier ou URL distante) — mutualisé (#83/#91).

`import_ics_bytes` applique la même logique de déduplication (par UID) et de
création de règles de récurrence, que la source soit un fichier téléversé ou une
URL .ics distante (ex. « adresse secrète au format iCal » de Google Calendar).
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import create_event, create_recurrence_rule
from app.services.agenda.ical_adapter import parse_ics


def import_ics_bytes(session: Session, content: bytes) -> dict[str, int]:
    """Importe un .ics (bytes). Retourne les compteurs created/skipped/rules."""
    parsed = parse_ics(content)
    created_events = skipped = created_rules = 0

    for item in parsed:
        rrule = item.pop("_rrule", None)
        uid = item.get("source_id", "")

        existing = session.exec(
            select(Evenement).where(Evenement.source_id == uid).where(Evenement.source == "ical")
        ).first() if uid else None
        if existing:
            skipped += 1
            continue

        rule_id = None
        if rrule:
            rule_data: dict[str, Any] = {
                "titre": item["titre"],
                "weekdays": rrule["weekdays"],
                "start_time": rrule["start_time"],
                "end_time": rrule["end_time"],
                "until": rrule["until"],
                "categorie": item.get("categorie"),
                "lieu": item.get("lieu"),
            }
            rule = create_recurrence_rule(session, rule_data)
            rule_id = rule.id
            created_rules += 1

        item["recurrence_id"] = rule_id
        create_event(session, item)
        created_events += 1

    return {
        "created_events": created_events,
        "skipped_duplicates": skipped,
        "created_rules": created_rules,
    }


def import_ics_from_url(session: Session, url: str, *, timeout: float = 15.0) -> dict[str, int]:
    """Récupère un .ics distant (ex. Agendrix) et l'importe (dédup par UID).

    Mutualisé entre la route `/agenda/sync-ical-url` et le job de synchro
    automatique. Lève ``ValueError`` si l'URL n'est pas http(s) et
    ``RuntimeError`` si la récupération échoue.
    """
    import httpx

    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL invalide (http/https attendu).")
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Récupération du calendrier impossible : {e}") from e
    return import_ics_bytes(session, resp.content)
