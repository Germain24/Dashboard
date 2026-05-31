import datetime as dt
from sqlmodel import SQLModel, Field

class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    id: int | None = Field(default=None, primary_key=True)
    source: str = "system"
    level: str = "info"
    titre: str
    message: str = ""
    lu: bool = False
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

class JobRun(SQLModel, table=True):
    __tablename__ = "job_run"
    id: int | None = Field(default=None, primary_key=True)
    job_id: str
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    status: str = "running"
    log: str = ""
