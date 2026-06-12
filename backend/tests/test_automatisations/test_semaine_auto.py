"""Tests TDD pour le remplissage auto de la semaine (#210)."""
import datetime as dt
import pytest
from tests.conftest import mem_session  # noqa: F401
from sqlmodel import select

from app.models.agenda import Evenement
from app.services.automatisations.semaine_auto import (
    suggest_sport_events,
    suggest_etudes_events,
    fill_week_auto,
)


def _monday(offset_weeks: int = 0) -> dt.date:
    today = dt.date.today()
    return today - dt.timedelta(days=today.weekday()) + dt.timedelta(weeks=offset_weeks)


class TestSuggestSportEvents:
    def test_returns_list_of_dicts(self, mem_session):
        monday = _monday(1)
        result = suggest_sport_events(mem_session, week_start=monday)
        assert isinstance(result, list)

    def test_events_have_required_keys(self, mem_session):
        from app.models.entrainement import Programme, ProgrammeJour
        prog = Programme(nom="Test", actif=True)
        mem_session.add(prog)
        mem_session.commit()
        mem_session.refresh(prog)
        # Lundi = sport
        pj = ProgrammeJour(programme_id=prog.id, weekday=0, label="Squat", slots=[{"exercice_id": 1}])
        mem_session.add(pj)
        mem_session.commit()

        monday = _monday(1)
        result = suggest_sport_events(mem_session, week_start=monday)
        if result:
            ev = result[0]
            assert "titre" in ev
            assert "debut" in ev
            assert "fin" in ev
            assert "categorie" in ev

    def test_rest_days_not_suggested(self, mem_session):
        from app.models.entrainement import Programme, ProgrammeJour
        prog = Programme(nom="Test", actif=True)
        mem_session.add(prog)
        mem_session.commit()
        mem_session.refresh(prog)
        # Lundi = repos (slots vides)
        pj = ProgrammeJour(programme_id=prog.id, weekday=0, label="Repos", slots=[])
        mem_session.add(pj)
        mem_session.commit()

        monday = _monday(1)
        result = suggest_sport_events(mem_session, week_start=monday)
        lundi_events = [e for e in result if e["debut"].date() == monday]
        assert lundi_events == []


class TestSuggestEtudesEvents:
    def test_returns_list(self, mem_session):
        monday = _monday(1)
        result = suggest_etudes_events(mem_session, week_start=monday)
        assert isinstance(result, list)

    def test_respects_heures_objectif(self, mem_session):
        from app.services.etudes.goals import set_weekly_hours
        set_weekly_hours(5.0)

        monday = _monday(1)
        result = suggest_etudes_events(mem_session, week_start=monday)
        total_min = sum(e.get("duree_min", 0) for e in result)
        # On veut ~5h = 300min, peut être moins si les créneaux sont complets
        assert total_min > 0

    def test_no_goal_no_suggestion(self, mem_session):
        from app.services.etudes.goals import set_weekly_hours
        set_weekly_hours(0.0)

        monday = _monday(1)
        result = suggest_etudes_events(mem_session, week_start=monday)
        assert result == []


class TestFillWeekAuto:
    def test_dry_run_creates_no_events(self, mem_session):
        monday = _monday(1)
        from app.services.etudes.goals import set_weekly_hours
        set_weekly_hours(2.0)
        result = fill_week_auto(mem_session, week_start=monday, dry_run=True)
        events = list(mem_session.exec(select(Evenement)).all())
        assert events == []
        assert isinstance(result, list)

    def test_creates_events_when_not_dry_run(self, mem_session):
        from app.services.etudes.goals import set_weekly_hours
        set_weekly_hours(2.0)
        monday = _monday(1)
        result = fill_week_auto(mem_session, week_start=monday, dry_run=False)
        events = list(mem_session.exec(
            select(Evenement).where(Evenement.source == "auto_semaine")
        ).all())
        assert len(events) == len(result)

    def test_idempotent_no_duplicates(self, mem_session):
        from app.services.etudes.goals import set_weekly_hours
        set_weekly_hours(2.0)
        monday = _monday(1)
        fill_week_auto(mem_session, week_start=monday, dry_run=False)
        fill_week_auto(mem_session, week_start=monday, dry_run=False)
        events = list(mem_session.exec(
            select(Evenement).where(Evenement.source == "auto_semaine")
        ).all())
        # Should not have duplicates
        debuts = [e.debut for e in events]
        assert len(debuts) == len(set(debuts))
