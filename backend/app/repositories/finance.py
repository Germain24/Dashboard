"""Repositories du module Finance."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.finance import (
    BuffettRun, BuffettRunResult, Position, SnapshotPortefeuille, Transaction,
)


class TransactionRepository(Repository[Transaction]):
    model = Transaction


class PositionRepository(Repository[Position]):
    model = Position


class SnapshotRepository(Repository[SnapshotPortefeuille]):
    model = SnapshotPortefeuille


class BuffettRunRepository(Repository[BuffettRun]):
    model = BuffettRun


class BuffettRunResultRepository(Repository[BuffettRunResult]):
    model = BuffettRunResult
