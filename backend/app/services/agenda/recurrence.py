"""Génération d'occurrences à partir d'une RegleRecurrence.

Format de règle : weekdays (list[int] 0=Lun…6=Dim), start_time "HH:MM",
end_time "HH:MM", until (date ou None).

Design : logique pure (pas de session DB). Les tests peuvent fonctionner
sans stack web (cf. PLAN.md note 10).
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def _parse_time(t: str) -> dt.time:
    h, m = map(int, t.split(":"))
    return dt.time(h, m)


def expand_rule(
    rule_id: int,
    titre: str,
    weekdays: list[int],
    start_time: str,
    end_time: str,
    from_date: dt.date,
    to_date: dt.date,
    until: dt.date | None = None,
    lieu: str | None = None,
    description: str | None = None,
    categorie: str | None = None,
    couleur: str | None = None,
) -> list[dict[str, Any]]:
    """Retourne les occurrences virtuelles dans [from_date, to_date].

    Chaque occurrence est un dict compatible avec EvenementRead (id=None
    signale que c'est une occurrence virtuelle, pas persistée).
    """
    effective_until = min(to_date, until) if until else to_date
    wd_set = set(weekdays)
    t_start = _parse_time(start_time)
    t_end = _parse_time(end_time)

    occurrences: list[dict[str, Any]] = []
    current = from_date
    while current <= effective_until:
        if current.weekday() in wd_set:
            occurrences.append(
                {
                    "id": None,
                    "titre": titre,
                    "debut": dt.datetime.combine(current, t_start),
                    "fin": dt.datetime.combine(current, t_end),
                    "lieu": lieu,
                    "description": description,
                    "source": "recurrence",
                    "source_id": None,
                    "categorie": categorie,
                    "couleur": couleur,
                    "recurrence_id": rule_id,
                    "is_virtual": True,
                }
            )
        current += dt.timedelta(days=1)
    return occurrences


def expand_rules_for_window(
    rules: list[Any],  # list[RegleRecurrence]
    from_date: dt.date,
    to_date: dt.date,
) -> list[dict[str, Any]]:
    """Expansion de toutes les règles pour une fenêtre temporelle."""
    result: list[dict[str, Any]] = []
    for r in rules:
        result.extend(
            expand_rule(
                rule_id=r.id,
                titre=r.titre,
                weekdays=list(r.weekdays or []),
                start_time=r.start_time,
                end_time=r.end_time,
                from_date=from_date,
                to_date=to_date,
                until=r.until,
                lieu=r.lieu,
                description=r.description,
                categorie=r.categorie,
                couleur=r.couleur,
            )
        )
    return result
