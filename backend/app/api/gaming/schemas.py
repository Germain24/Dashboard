from pydantic import BaseModel, Field

STATUTS = ("backlog", "en_cours", "termine", "abandonne")
GOAL_TYPES = ("objectif", "build", "filtre")


class GameCreate(BaseModel):
    titre: str = Field(min_length=1)
    plateforme: str = "PC"
    statut: str = "backlog"
    note: int | None = Field(default=None, ge=0, le=10)
    heures: float = Field(default=0.0, ge=0)


class GameUpdate(BaseModel):
    titre: str | None = Field(default=None, min_length=1)
    plateforme: str | None = None
    statut: str | None = None
    note: int | None = Field(default=None, ge=0, le=10)
    heures: float | None = Field(default=None, ge=0)


class GoalCreate(BaseModel):
    titre: str = Field(min_length=1)
    type: str = "objectif"
    contenu: str | None = None
    fait: bool = False


class GoalUpdate(BaseModel):
    titre: str | None = Field(default=None, min_length=1)
    type: str | None = None
    contenu: str | None = None
    fait: bool | None = None
