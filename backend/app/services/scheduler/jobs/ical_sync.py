"""Synchro automatique des calendriers iCal externes (ex. Agendrix).

Re-télécharge périodiquement les URLs .ics configurées dans
``settings.ical_sync_urls`` et les importe (dédup par UID via import_ics_bytes).
Aucune URL configurée = job inactif (retour explicite, pas d'erreur).
"""

from __future__ import annotations


def run(session) -> str:
    from app.core.config import settings
    from app.services.agenda.ical_import import import_ics_from_url
    from app.services.agenda import ical_source

    source = ical_source.source_for_sync()
    urls = settings.ical_sync_url_list
    if source["url"] and source["enabled"]:
        urls = [url for url in urls if url != source["url"]]
    if not urls and not (source["url"] and source["enabled"]):
        return "iCal sync: aucune URL configurée"

    total_created = 0
    total_updated = 0
    total_deleted = 0
    total_skipped = 0
    erreurs = 0
    if source["url"] and source["enabled"]:
        try:
            counts = ical_source.sync(session)
            total_created += counts["created_events"]
            total_updated += counts.get("updated_events", 0)
            total_deleted += counts.get("deleted_events", 0)
            total_skipped += counts["skipped_duplicates"]
        except Exception:  # noqa: BLE001
            erreurs += 1
    for url in urls:
        try:
            counts = import_ics_from_url(session, url)
            total_created += counts["created_events"]
            total_updated += counts.get("updated_events", 0)
            total_deleted += counts.get("deleted_events", 0)
            total_skipped += counts["skipped_duplicates"]
        except Exception:  # noqa: BLE001
            erreurs += 1

    suffix = f", {erreurs} échec(s)" if erreurs else ""
    return (
        f"iCal sync: {total_created} ajouté(s), {total_updated} mis à jour(s), {total_deleted} retiré(s), "
        f"{total_skipped} déjà présent(s){suffix}"
    )
