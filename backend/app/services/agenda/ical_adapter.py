"""Parseur iCalendar (.ics) → Evenement (CONV 5 V1).

Dépendance : `icalendar` (RFC 5545).
Stratégie : importer chaque VEVENT comme Evenement persisté.
  - RRULE → on crée une RegleRecurrence + un Evenement seed (first occurrence).
  - UID iCal → stocké dans source_id pour déduplication (skip si déjà importé).

V1 scope : VEVENT ponctuels + RRULE hebdo simple (FREQ=WEEKLY;BYDAY=...).
V2 futur : EXDATE, VTIMEZONE, sync bidirectionnel Google.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

log = logging.getLogger(__name__)

_BYDAY_MAP = {
    "MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6,
}


def _to_datetime(val: Any, tzinfo=None) -> dt.datetime:
    """Convertit vDate / vDatetime → datetime naïf (UTC→local ignoré en V1)."""
    if isinstance(val, dt.datetime):
        return val.replace(tzinfo=None)
    if isinstance(val, dt.date):
        return dt.datetime(val.year, val.month, val.day, 0, 0)
    return dt.datetime.utcnow()


def parse_ics(content: bytes) -> list[dict[str, Any]]:
    """Parse un fichier .ics et retourne une liste de dicts prêts à insérer.

    Chaque dict contient les clés d'Evenement + clé spéciale `_rrule` (dict
    ou None) utilisée par routes_agenda pour créer RegleRecurrence si besoin.

    `_rrule` = { weekdays: list[int], start_time: str, end_time: str, until: date|None }
    """
    try:
        from icalendar import Calendar
    except ImportError:
        log.error("Lib `icalendar` manquante — pip install icalendar")
        return []

    try:
        cal = Calendar.from_ical(content)
    except Exception as e:
        log.warning("Erreur parse .ics : %s", e)
        return []

    results: list[dict[str, Any]] = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue

        uid = str(comp.get("UID", ""))
        summary = str(comp.get("SUMMARY", "Sans titre"))
        location = str(comp.get("LOCATION", "")) or None
        description = str(comp.get("DESCRIPTION", "")) or None

        dtstart = comp.get("DTSTART")
        dtend = comp.get("DTEND")
        debut = _to_datetime(dtstart.dt) if dtstart else dt.datetime.utcnow()
        fin = _to_datetime(dtend.dt) if dtend else debut + dt.timedelta(hours=1)

        rrule_raw = comp.get("RRULE")
        rrule_dict: dict[str, Any] | None = None

        if rrule_raw:
            rrule = rrule_raw
            freq = str(rrule.get("FREQ", [""])[0]).upper()
            if freq == "WEEKLY":
                byday = [str(d) for d in rrule.get("BYDAY", [])]
                weekdays = [_BYDAY_MAP[d] for d in byday if d in _BYDAY_MAP]
                until_raw = rrule.get("UNTIL", [None])[0]
                until: dt.date | None = None
                if until_raw:
                    until = _to_datetime(until_raw).date()
                rrule_dict = {
                    "weekdays": weekdays or [debut.weekday()],
                    "start_time": debut.strftime("%H:%M"),
                    "end_time": fin.strftime("%H:%M"),
                    "until": until,
                }

        results.append({
            "titre": summary,
            "debut": debut,
            "fin": fin,
            "lieu": location,
            "description": description,
            "source": "ical",
            "source_id": uid,
            "_rrule": rrule_dict,
        })

    return results
