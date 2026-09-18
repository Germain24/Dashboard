import datetime as dt

from pydantic import BaseModel, Field

STATUTS = ("prevu", "fait", "annule")


class ShiftCreate(BaseModel):
    date_jour: dt.date
    heure_debut: str = "09:00"
    heure_fin: str = "17:00"
    pause_min: int = Field(default=0, ge=0)
    taux_horaire: float | None = Field(default=None, ge=0)
    role: str = "barista"
    statut: str = "prevu"
    note: str | None = None


class ShiftUpdate(BaseModel):
    date_jour: dt.date | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    pause_min: int | None = Field(default=None, ge=0)
    taux_horaire: float | None = Field(default=None, ge=0)
    role: str | None = None
    statut: str | None = None
    note: str | None = None


class TauxHoraireUpdate(BaseModel):
    taux_horaire: float = Field(ge=0)
