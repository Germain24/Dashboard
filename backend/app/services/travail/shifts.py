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
