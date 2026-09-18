import datetime as dt

from pydantic import BaseModel, Field

VOCAB_TYPES = ("vocab", "kanji")
PROJET_TYPES = ("semestre", "visa", "voyage", "autre")
PROJET_STATUTS = ("idee", "planifie", "en_cours", "fait")


class VocabCreate(BaseModel):
    terme: str = Field(min_length=1)
    lecture: str | None = None
    traduction: str = Field(min_length=1)
    type: str = "vocab"
    tags: str | None = None
    maitrise: int = Field(default=0, ge=0, le=5)


class VocabUpdate(BaseModel):
    terme: str | None = Field(default=None, min_length=1)
    lecture: str | None = None
    traduction: str | None = Field(default=None, min_length=1)
    type: str | None = None
    tags: str | None = None
    maitrise: int | None = Field(default=None, ge=0, le=5)


class ProjetCreate(BaseModel):
    titre: str = Field(min_length=1)
    type: str = "voyage"
    statut: str = "idee"
    echeance: dt.date | None = None
    budget_estime: float | None = Field(default=None, ge=0)
    notes: str | None = None


class ProjetUpdate(BaseModel):
    titre: str | None = Field(default=None, min_length=1)
    type: str | None = None
    statut: str | None = None
    echeance: dt.date | None = None
    budget_estime: float | None = Field(default=None, ge=0)
    notes: str | None = None
