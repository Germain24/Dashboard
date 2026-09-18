"""Helpers partagés entre les sous-routeurs Agenda (#502)."""
from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.api.agenda.schemas import EvenementRead
from app.core.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def ev_to_read(d: dict) -> EvenementRead:
    return EvenementRead(**d)


def dates_in_range(start: dt.date, end: dt.date) -> list[dt.date]:
    result = []
    cur = start
    while cur <= end:
        result.append(cur)
        cur += dt.timedelta(days=1)
    return result
