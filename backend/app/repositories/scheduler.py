"""Repositories du module Scheduler / Notifications."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.scheduler import JobRun, Notification


class JobRunRepository(Repository[JobRun]):
    model = JobRun


class NotificationRepository(Repository[Notification]):
    model = Notification
