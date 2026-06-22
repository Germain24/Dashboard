"""Routine « semaine auto » → délègue au planificateur unique (source=planner)."""
import datetime as dt
from tests.conftest import mem_session  # noqa: F401
from sqlmodel import select

from app.models.agenda import Evenement
from app.services.automatisations.semaine_auto import fill_week_auto


def _thursday(offset_weeks: int = 1) -> dt.date:
    """Un jeudi futur (jour de lancement de cycle → fenêtre ven→dim)."""
    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday()) + dt.timedelta(weeks=offset_weeks)
    return monday + dt.timedelta(days=3)


class TestFillWeekAuto:
    def test_dry_run_creates_no_events(self, mem_session):
        result = fill_week_auto(mem_session, week_start=_thursday(), dry_run=True)
        assert isinstance(result, list)
        assert list(mem_session.exec(select(Evenement)).all()) == []

    def test_commit_creates_planner_events(self, mem_session):
        thu = _thursday()
        result = fill_week_auto(mem_session, week_start=thu, dry_run=False)
        assert result  # le cycle contient au moins sommeil/repas
        events = list(mem_session.exec(
            select(Evenement).where(Evenement.source == "planner")
        ).all())
        assert len(events) == len(result)
        # plus AUCUN événement de l'ancien planificateur parallèle
        assert list(mem_session.exec(
            select(Evenement).where(Evenement.source == "auto_semaine")
        ).all()) == []

    def test_idempotent_no_duplicates(self, mem_session):
        thu = _thursday()
        fill_week_auto(mem_session, week_start=thu, dry_run=False)
        fill_week_auto(mem_session, week_start=thu, dry_run=False)
        events = list(mem_session.exec(
            select(Evenement).where(Evenement.source == "planner")
        ).all())
        debuts = [(e.titre, e.debut) for e in events]
        assert len(debuts) == len(set(debuts))   # pas de doublons
