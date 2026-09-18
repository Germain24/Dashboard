"""Planification hebdomadaire des révisions, Shopify prioritaire."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models.agenda import Evenement, RegleRecurrence
from app.services.agenda.weekly_revisions import (
    HOME_SESSION_MIN,
    SHOPIFY_SESSION_MIN,
    plan_weekly_revisions,
    replan_current_weekly_revisions,
    run_weekly_revisions,
)

SUNDAY = dt.date(2026, 9, 13)
SATURDAY = dt.date(2026, 9, 12)


def _at(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute))


def _minutes(block) -> int:
    return int((block.fin - block.debut).total_seconds() / 60)


def test_prefers_shopify_then_falls_back_home_with_course_targets():
    proposal = plan_weekly_revisions(
        SUNDAY,
        ["Économie", "Macro", "Programmation", "Économétrie"],
        {},
    )

    shopify = [block for block in proposal.blocks if block.lieu == "Shopify"]
    home = [block for block in proposal.blocks if block.lieu == "Maison"]
    assert len(shopify) == 3  # un repas peut être pris pendant une séance
    assert all(_minutes(block) == SHOPIFY_SESSION_MIN for block in shopify)
    assert len(home) == 1
    assert all(_minutes(block) == HOME_SESSION_MIN for block in home)
    assert len({block.course for block in proposal.blocks}) == 4
    assert proposal.non_places == []
    assert min(block.debut for block in shopify) == _at(SUNDAY, 12)
    assert all(block.debut >= _at(SUNDAY, 12) for block in shopify)
    assert [block.debut for block in shopify] == [
        _at(SUNDAY, 12), _at(SUNDAY, 13, 45), _at(SUNDAY, 15, 30)
    ]


def test_work_during_shopify_window_wins_and_revision_moves_home():
    shift = (_at(SUNDAY, 12), _at(SUNDAY, 17))
    proposal = plan_weekly_revisions(
        SUNDAY,
        ["Économie", "Macro"],
        {SUNDAY: [shift]},
    )

    assert len(proposal.blocks) == 2
    assert all(block.lieu == "Maison" for block in proposal.blocks)
    assert all(_minutes(block) == HOME_SESSION_MIN for block in proposal.blocks)
    assert all(block.fin <= shift[0] or block.debut >= shift[1] for block in proposal.blocks)


def test_duplicate_class_meetings_get_one_weekly_revision():
    proposal = plan_weekly_revisions(SUNDAY, ["Macro", "Macro"], {})
    assert len(proposal.blocks) == 1
    assert proposal.blocks[0].course == "Macro"


def test_job_builds_and_rebuilds_one_shopify_revision_from_weekly_rule():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            RegleRecurrence(
                titre="Macroéconomie II",
                weekdays=[1],
                start_time="14:00",
                end_time="17:00",
                categorie="cours",
                until=dt.date(2026, 12, 25),
            )
        )
        session.commit()

        run_weekly_revisions(session, SATURDAY)
        first = session.exec(select(Evenement).where(Evenement.source == "revision_planner")).all()
        assert len(first) == 1
        assert first[0].lieu == "Shopify"
        assert _minutes(first[0]) == SHOPIFY_SESSION_MIN

        run_weekly_revisions(session, SATURDAY)
        rebuilt = session.exec(
            select(Evenement).where(Evenement.source == "revision_planner")
        ).all()
        assert len(rebuilt) == 1


def test_manual_replan_targets_the_week_already_in_progress(monkeypatch):
    from app.services.agenda import preferences

    monkeypatch.setattr(preferences, "get_preferences", lambda: {"moments": {}})
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            RegleRecurrence(
                titre="Économie",
                weekdays=[1],
                start_time="09:00",
                end_time="12:00",
                categorie="cours",
                until=SUNDAY + dt.timedelta(days=30),
            )
        )
        session.commit()

        replan_current_weekly_revisions(session, SUNDAY + dt.timedelta(days=2))
        blocks = session.exec(select(Evenement).where(Evenement.source == "revision_planner")).all()

    assert len(blocks) == 1
    assert blocks[0].debut.date() >= SUNDAY
    assert blocks[0].debut.date() < SUNDAY + dt.timedelta(days=7)
