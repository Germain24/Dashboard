import datetime as dt
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint

class Habit(SQLModel, table=True):
    __tablename__ = "habit"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    type: str = "binaire"
    unite: str | None = None
    cible: float = 1.0
    frequence: str = "daily"
    source_auto: str | None = None
    actif: bool = True
    ordre: int = 0
    couleur: str | None = None  # #RRGGBB ou nom CSS
    icone: str | None = None    # emoji ou identifiant Lucide
    linked_ids: str = "[]"      # JSON list[int] — IDs des habitudes auto-cochées

class HabitEntry(SQLModel, table=True):
    __tablename__ = "habit_entry"
    id: int | None = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id")
    date: dt.date
    valeur: float = 1.0
    auto: bool = False
    __table_args__ = (UniqueConstraint("habit_id", "date"),)
