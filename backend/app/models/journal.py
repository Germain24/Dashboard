"""Module Journal / Humeur (#476) — suivi d'humeur quotidien, sans IA."""
import datetime as dt

from sqlmodel import Column, Field, JSON, SQLModel


class MoodEntry(SQLModel, table=True):
    __tablename__ = "mood_entry"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True, unique=True)  # une entrée par jour
    humeur: int          # 1-5
    energie: int         # 1-5
    tags: list = Field(default_factory=list, sa_column=Column(JSON))
    note: str = ""
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
