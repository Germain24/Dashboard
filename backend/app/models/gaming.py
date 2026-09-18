from sqlmodel import Field, SQLModel


class Game(SQLModel, table=True):
    """Jeu suivi dans le carnet de bord joueur."""

    __tablename__ = "game"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    plateforme: str = "PC"
    statut: str = "backlog"  # backlog|en_cours|termine|abandonne
    note: int | None = None  # 0-10
    heures: float = 0.0


class GameGoal(SQLModel, table=True):
    """Objectif, build de personnage ou filtre d'items rattaché à un jeu."""

    __tablename__ = "game_goal"
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id")
    titre: str
    type: str = "objectif"  # objectif|build|filtre
    contenu: str | None = None
    fait: bool = False
