"""Repositories du module Garderobe."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.garderobe import TenueHistory, Vetement


class VetementRepository(Repository[Vetement]):
    model = Vetement


class TenueHistoryRepository(Repository[TenueHistory]):
    model = TenueHistory
