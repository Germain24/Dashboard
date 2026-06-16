import datetime as dt

from pydantic import BaseModel, Field

CATEGORIES = ("master", "concours", "carriere", "autre")
STATUTS = ("veille", "preparation", "candidature", "obtenu", "abandonne")


class GoalCreate(BaseModel):
    titre: str = Field(min_length=1)
    categorie: str = "autre"
    statut: str = "veille"
    echeance: dt.date | None = None
    progression: int = Field(default=0, ge=0, le=100)
    description: str | None = None
    lien: str | None = None


class GoalUpdate(BaseModel):
    titre: str | None = Field(default=None, min_length=1)
    categorie: str | None = None
    statut: str | None = None
    echeance: dt.date | None = None
    progression: int | None = Field(default=None, ge=0, le=100)
    description: str | None = None
    lien: str | None = None
