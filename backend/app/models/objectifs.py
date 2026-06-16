import datetime as dt

from sqlmodel import Field, SQLModel


class LongTermGoal(SQLModel, table=True):
    """Objectif long terme : masters, concours, opportunités carrière."""

    __tablename__ = "long_term_goal"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    categorie: str = "autre"  # master|concours|carriere|autre
    statut: str = "veille"    # veille|preparation|candidature|obtenu|abandonne
    echeance: dt.date | None = None
    progression: int = 0      # 0-100
    description: str | None = None
    lien: str | None = None
    cree_le: dt.date = Field(default_factory=dt.date.today)
