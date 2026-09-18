"""Calculs du module Travail : durée d'un shift, résumé mensuel heures/revenus."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.travail import WorkShift
from app.services.travail.settings import get_taux_horaire


def duree_heures(shift: WorkShift) -> float:
    """Durée travaillée en heures, pause déduite. 0 si bornes incohérentes."""
    try:
        debut = dt.datetime.strptime(shift.heure_debut, "%H:%M")
        fin = dt.datetime.strptime(shift.heure_fin, "%H:%M")
    except ValueError:
        return 0.0
    minutes = (fin - debut).total_seconds() / 60 - shift.pause_min
    return max(round(minutes / 60, 2), 0.0)


def revenu(shift: WorkShift, taux_defaut: float) -> float:
    taux = shift.taux_horaire if shift.taux_horaire is not None else taux_defaut
    return round(duree_heures(shift) * taux, 2)


def list_shifts_for_window(
    session: Session, from_dt: dt.datetime, to_dt: dt.datetime
) -> list[dict]:
    """Shifts de travail non annulés dans une fenêtre, au format bloc agenda.

    Renvoie [{debut: datetime, fin: datetime, titre: str}] — compatible avec
    le planificateur (obstacles fixes, peuvent chevaucher les repas).
    """
    from sqlalchemy import and_

    shifts = session.exec(
        select(WorkShift).where(
            and_(
                WorkShift.date_jour >= from_dt.date(),
                WorkShift.date_jour <= to_dt.date(),
                WorkShift.statut != "annule",
            )
        )
    ).all()
    result = []
    for s in shifts:
        try:
            debut = dt.datetime.combine(s.date_jour, dt.datetime.strptime(s.heure_debut, "%H:%M").time())
            fin = dt.datetime.combine(s.date_jour, dt.datetime.strptime(s.heure_fin, "%H:%M").time())
            result.append({"debut": debut, "fin": fin, "titre": f"Travail — {s.lieu or 'Barista'}"})
        except (ValueError, TypeError):
            continue
    return result


def summary(session: Session, mois: str) -> dict:
    """Résumé d'un mois (YYYY-MM) : heures et revenus, réalisés vs prévus."""
    annee, mois_num = (int(x) for x in mois.split("-"))
    debut = dt.date(annee, mois_num, 1)
    fin = dt.date(annee + 1, 1, 1) if mois_num == 12 else dt.date(annee, mois_num + 1, 1)
    shifts = session.exec(
        select(WorkShift).where(WorkShift.date_jour >= debut, WorkShift.date_jour < fin)
    ).all()
    taux_defaut = get_taux_horaire()
    faits = [s for s in shifts if s.statut == "fait"]
    prevus = [s for s in shifts if s.statut == "prevu"]
    return {
        "mois": mois,
        "taux_horaire_defaut": taux_defaut,
        "nb_shifts": len([s for s in shifts if s.statut != "annule"]),
        "heures_faites": round(sum(duree_heures(s) for s in faits), 2),
        "heures_prevues": round(sum(duree_heures(s) for s in prevus), 2),
        "revenu_realise": round(sum(revenu(s, taux_defaut) for s in faits), 2),
        "revenu_prevu": round(sum(revenu(s, taux_defaut) for s in prevus), 2),
    }
