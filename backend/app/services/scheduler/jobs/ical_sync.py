"""Synchro automatique des calendriers iCal externes (ex. Agendrix).

Re-télécharge périodiquement les URLs .ics configurées dans
``settings.ical_sync_urls`` et les importe (dédup par UID via import_ics_bytes).
Aucune URL configurée = job inactif (retour explicite, pas d'erreur).
"""

from __future__ import annotations


def run(session) -> str:
    from app.core.config import settings
    from app.services.agenda.ical_import import import_ics_from_url

    urls = settings.ical_sync_url_list
    if not urls:
        return "iCal sync: aucune URL configurée"

    total_created = 0
    total_skipped = 0
    erreurs = 0
    for url in urls:
        try:
            counts = import_ics_from_url(session, url)
            total_created += counts["created_events"]
            total_skipped += counts["skipped_duplicates"]
        except Exception:  # noqa: BLE001
            erreurs += 1

    suffix = f", {erreurs} échec(s)" if erreurs else ""
    return f"iCal sync: {total_created} ajouté(s), {total_skipped} déjà présent(s){suffix}"
