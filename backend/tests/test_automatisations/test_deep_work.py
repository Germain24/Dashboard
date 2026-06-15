"""Tests TDD — planificateur deep work (#220)."""

from __future__ import annotations

import datetime as dt

from tests.conftest import mem_session  # noqa: F401
from sqlmodel import select

from app.models.agenda import Evenement
from app.services.automatisations.deep_work import (
    plan_deep_work,
    select_deep_work_blocks,
)


def _slot(day: dt.date, hour: int, duree_min: int = 120) -> dict:
    return {"debut": dt.datetime.combine(day, dt.time(hour, 0)), "duree_min": duree_min}


D = dt.date(2026, 6, 15)  # lundi


# ── Fonction pure ───────────────────────────────────────────────────────────--

def test_places_on_lighter_days_first():
    days = [
        {"load_min": 400, "slots": [_slot(D, 9)]},
        {"load_min": 30, "slots": [_slot(D + dt.timedelta(days=1), 9)]},
    ]
    blocks = select_deep_work_blocks(days, n_blocks=1, block_min=90)
    assert len(blocks) == 1
    assert blocks[0]["debut"].date() == D + dt.timedelta(days=1)  # jour le moins chargé


def test_respects_max_per_day():
    days = [{"load_min": 0, "slots": [_slot(D, 9), _slot(D, 12), _slot(D, 15)]}]
    blocks = select_deep_work_blocks(days, n_blocks=10, block_min=90, max_per_day=2)
    assert len(blocks) == 2


def test_caps_at_n_blocks():
    days = [{"load_min": i, "slots": [_slot(D + dt.timedelta(days=i), 9)]} for i in range(7)]
    blocks = select_deep_work_blocks(days, n_blocks=3, block_min=90, max_per_day=1)
    assert len(blocks) == 3


def test_skips_slots_too_short():
    days = [{"load_min": 0, "slots": [_slot(D, 9, duree_min=45)]}]
    assert select_deep_work_blocks(days, n_blocks=5, block_min=90) == []


def test_blocks_have_focus_metadata_and_sorted():
    days = [{"load_min": 0, "slots": [_slot(D, 15)]}, {"load_min": 0, "slots": [_slot(D, 9)]}]
    blocks = select_deep_work_blocks(days, n_blocks=2, block_min=90, max_per_day=1)
    assert [b["debut"].hour for b in blocks] == [9, 15]  # trié par début
    assert all(b["categorie"] == "focus" and b["source"] == "deep_work" for b in blocks)
    assert all(b["duree_min"] == 90 for b in blocks)


# ── Intégration base ────────────────────────────────────────────────────────--

def test_plan_dry_run_does_not_persist(mem_session):
    blocks = plan_deep_work(mem_session, D, n_blocks=2, dry_run=True)
    assert len(blocks) >= 1
    assert mem_session.exec(select(Evenement).where(Evenement.source == "deep_work")).all() == []


def test_plan_persists_and_is_idempotent(mem_session):
    first = plan_deep_work(mem_session, D, n_blocks=2, dry_run=False)
    assert len(first) >= 1
    persisted = mem_session.exec(select(Evenement).where(Evenement.source == "deep_work")).all()
    assert len(persisted) == len(first)
    # 2e appel : aucun doublon créé
    second = plan_deep_work(mem_session, D, n_blocks=2, dry_run=False)
    assert second == []
    total = mem_session.exec(select(Evenement).where(Evenement.source == "deep_work")).all()
    assert len(total) == len(first)


def test_plan_avoids_busy_blocks(mem_session):
    # occupe 9h-18h lundi -> pas de bloc de 90 min ce jour-là dans 8-20h hormis 8-9 (60<90) / 18-20
    busy = Evenement(
        titre="Boulot", debut=dt.datetime.combine(D, dt.time(9, 0)),
        fin=dt.datetime.combine(D, dt.time(18, 0)), source="manuel",
    )
    mem_session.add(busy)
    mem_session.commit()
    blocks = plan_deep_work(mem_session, D, n_blocks=7, block_min=90, dry_run=True)
    monday_blocks = [b for b in blocks if b["debut"].date() == D]
    # le seul créneau ≥90 min lundi est 18-20h (1 bloc), pas de chevauchement avec 9-18h
    for b in monday_blocks:
        assert b["debut"] >= dt.datetime.combine(D, dt.time(18, 0))
