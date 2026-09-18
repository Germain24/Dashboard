"""Job de rappels d'agenda : pas de doublon de rappel muscu (#doublon muscu).

`agenda_reminders.run()` combine get_full_calendar() + get_training_block_for_date()
indépendamment de /agenda/today : sans dédoublonnage, un événement "Musculation"
synchronisé (gcal/.ics, donc sans `categorie`) génère un rappel EN PLUS du
rappel pour le bloc "Entraînement — X" du bridge, pour la même séance.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models.scheduler import Notification
from app.services.agenda.events import create_event
from app.services.entrainement import create_session as create_seance


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Le job lit/écrit des fichiers réels (préférences, clés déjà rappelées) via
    `settings.data_dir` (property calculée, non settable) : on isole les deux
    stores concernés dans un répertoire jetable pour ne jamais toucher les
    données réelles de l'app pendant le test."""
    import app.services.settings as settings_module
    import app.services.agenda.reminders as reminders_module

    monkeypatch.setattr(
        settings_module, "_store", settings_module.SettingsStore(path=tmp_path / "app_settings.json")
    )
    monkeypatch.setattr(reminders_module, "reminded_file", lambda: tmp_path / "agenda_reminded.json")


def test_run_does_not_duplicate_reminder_for_synced_workout_event(session):
    from app.services.scheduler.jobs.agenda_reminders import run

    now = dt.datetime.now().replace(second=0, microsecond=0)
    start = now + dt.timedelta(minutes=10)  # dans la fenêtre de rappel (30 min)

    # Séance réellement loggée (le bridge produit un bloc "Entraînement — push"
    # à l'heure réelle `start`).
    create_seance(session, date=start, type="push", duree_min=45)

    # Événement synchronisé depuis Google Calendar pour la même séance : jamais
    # de `categorie` (cf. gcal_to_evenement), donc invisible à l'ancien filtre
    # `categorie == "sport"`.
    create_event(session, {
        "titre": "Musculation",
        "debut": start,
        "fin": start + dt.timedelta(minutes=60),
        "source": "gcal",
        "source_id": "gcal-evt-reminder",
    })

    result = run(session)

    notifs = session.exec(
        select(Notification).where(Notification.source == "agenda_reminder")
    ).all()
    assert len(notifs) == 1, (
        f"un seul rappel attendu pour la séance, pas un doublon : "
        f"{[n.titre for n in notifs]} ({result})"
    )
