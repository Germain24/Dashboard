"""Import d'événements iCal (fichier ou URL distante) — mutualisé (#83/#91).

`import_ics_bytes` applique la même logique de déduplication (par UID) et de
création de règles de récurrence, que la source soit un fichier téléversé ou une
URL .ics distante (ex. « adresse secrète au format iCal » de Google Calendar).
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from urllib.parse import urljoin, urlparse

from sqlmodel import Session, select

from app.models.agenda import Evenement
from app.services.agenda.events import create_event, create_recurrence_rule
from app.services.agenda.ical_adapter import parse_ics


def import_ics_bytes(
    session: Session,
    content: bytes,
    *,
    source_key: str | None = None,
    category: str | None = None,
    prune_missing: bool = False,
) -> dict[str, int]:
    """Importe un .ics et synchronise les changements des UID déjà connus.

    ``source_key`` espace les UID quand plusieurs calendriers sont importés.
    ``category`` permet de classer explicitement une source, par exemple les
    shifts de travail. Les événements qui n'ont pas changé restent comptés
    parmi ``skipped_duplicates`` pour garder le contrat historique.
    """
    parsed = parse_ics(content)
    created_events = updated_events = deleted_events = skipped = created_rules = 0
    seen_uids: set[str] = set()

    for item in parsed:
        rrule = item.pop("_rrule", None)
        raw_uid = item.get("source_id", "")
        uid = f"{source_key}:{raw_uid}" if source_key and raw_uid else raw_uid
        item["source_id"] = uid
        if uid:
            seen_uids.add(uid)
        if category:
            item["categorie"] = category

        existing = session.exec(
            select(Evenement)
            .where(Evenement.source_id.in_([uid, raw_uid] if uid != raw_uid else [uid]))
            .where(Evenement.source == "ical")
        ).first() if uid else None
        if existing:
            updates = {
                "titre": item["titre"],
                "debut": item["debut"],
                "fin": item["fin"],
                "lieu": item.get("lieu"),
                "description": item.get("description"),
                "source_id": uid,
            }
            if category:
                updates["categorie"] = category
            changed = any(getattr(existing, key) != value for key, value in updates.items())
            if changed:
                for key, value in updates.items():
                    setattr(existing, key, value)
                session.add(existing)
                session.commit()
                updated_events += 1
            else:
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
        item.pop("_rrule", None)
        create_event(session, item)
        created_events += 1

    if prune_missing and source_key:
        prefix = f"{source_key}:"
        future_events = session.exec(
            select(Evenement)
            .where(Evenement.source == "ical")
            .where(Evenement.source_id.startswith(prefix))
            .where(Evenement.debut >= dt.datetime.now())
        ).all()
        for event in future_events:
            if event.source_id not in seen_uids:
                session.delete(event)
                deleted_events += 1
        if deleted_events:
            session.commit()

    return {
        "created_events": created_events,
        "updated_events": updated_events,
        "deleted_events": deleted_events,
        "skipped_duplicates": skipped,
        "created_rules": created_rules,
    }


def import_ics_from_url(
    session: Session,
    url: str,
    *,
    timeout: float = 15.0,
    source_key: str | None = None,
    category: str | None = None,
    prune_missing: bool = False,
) -> dict[str, int]:
    """Récupère un .ics distant (ex. Agendrix) et l'importe (dédup par UID).

    Mutualisé entre la route `/agenda/sync-ical-url` et le job de synchro
    automatique. Lève ``ValueError`` si l'URL n'est pas http(s) et
    ``RuntimeError`` si la récupération échoue.
    """
    import httpx

    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL invalide (lien HTTPS public attendu).")
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("L'URL du calendrier doit pointer vers un hôte public.")
    current_url = url
    initial_host = parsed.hostname.lower()
    try:
        # Follow only same-host HTTPS redirects, never forwarding the private
        # feed token to another domain. Stream with a hard 5 MB limit.
        for _ in range(4):
            with httpx.stream(
                "GET",
                current_url,
                timeout=timeout,
                follow_redirects=False,
                headers={"User-Agent": "MissionControl-iCal/1.0"},
            ) as resp:
                status_code = getattr(resp, "status_code", 200)
                if 300 <= status_code < 400:
                    location = resp.headers.get("location")
                    target = urljoin(current_url, location or "")
                    target_parts = urlparse(target)
                    if (
                        not location
                        or target_parts.scheme.lower() != "https"
                        or not target_parts.hostname
                        or target_parts.hostname.lower() != initial_host
                        or target_parts.username
                        or target_parts.password
                    ):
                        raise RuntimeError("Redirection iCal refusée.")
                    current_url = target
                    continue
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                try:
                    too_large = content_length is not None and int(content_length) > 5_000_000
                except ValueError:
                    too_large = False
                if too_large:
                    raise RuntimeError("Le calendrier dépasse la limite de 5 Mo.")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 5_000_000:
                        raise RuntimeError("Le calendrier dépasse la limite de 5 Mo.")
                break
        else:
            raise RuntimeError("Trop de redirections iCal.")
    except Exception as e:  # noqa: BLE001
        if isinstance(e, RuntimeError) and "limite" in str(e):
            raise
        raise RuntimeError("Récupération du calendrier impossible.") from e
    return import_ics_bytes(
        session,
        bytes(body),
        source_key=source_key,
        category=category,
        prune_missing=prune_missing,
    )
