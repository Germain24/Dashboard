"""Job rappel mensuel de mise à jour du score de crédit (#credit-reminder).

Exécuté le 5 de chaque mois. Si aucun rappel n'a encore été envoyé ce
mois-ci, crée une Notification invitant à saisir une nouvelle entrée de
score de crédit (`CreditScoreEntry`, module "Marge de crédit").
"""

from __future__ import annotations

import datetime as dt

from app.models.scheduler import Notification
from app.services.finance.credit.reminders import should_remind, mark_reminded


def run(session) -> str:
    from app.services.settings import get_preferences
    if get_preferences().get("mode_vacances"):
        return "Mode vacances actif — rappels suspendus"

    today = dt.date.today()
    if not should_remind(today):
        return "Rappel déjà envoyé ce mois-ci"

    session.add(Notification(
        source="credit_reminder",
        level="info",
        titre="📊 Mise à jour du score de crédit",
        message="Pense à ajouter la nouvelle entrée de score de crédit du mois (module Marge de crédit).",
    ))
    session.commit()
    mark_reminded(today)
    return "Rappel créé"
