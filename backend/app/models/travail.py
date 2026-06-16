import datetime as dt

from sqlmodel import Field, SQLModel


class WorkShift(SQLModel, table=True):
    """Shift de travail (barista) : planification, validation, revenus."""

    __tablename__ = "work_shift"
    id: int | None = Field(default=None, primary_key=True)
    date_jour: dt.date
    heure_debut: str = "09:00"  # HH:MM
    heure_fin: str = "17:00"    # HH:MM
    pause_min: int = 0
    # Taux horaire figé au moment du shift ; None → taux par défaut des settings.
    taux_horaire: float | None = None
    role: str = "barista"
    statut: str = "prevu"  # prevu|fait|annule
    note: str | None = None
