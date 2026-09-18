import datetime as dt

from sqlmodel import Field, SQLModel


class VocabEntry(SQLModel, table=True):
    """Entrée d'apprentissage du japonais : vocabulaire ou kanji."""

    __tablename__ = "vocab_entry"
    id: int | None = Field(default=None, primary_key=True)
    terme: str               # mot ou kanji
    lecture: str | None = None  # kana / romaji
    traduction: str
    type: str = "vocab"      # vocab|kanji
    tags: str | None = None  # CSV libre : "JLPT N5,verbe"
    maitrise: int = 0        # 0-5
    cree_le: dt.date = Field(default_factory=dt.date.today)


class ProjetInternational(SQLModel, table=True):
    """Projet du masterplan Asie : semestre, visa, itinéraire de voyage."""

    __tablename__ = "projet_international"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    type: str = "voyage"     # semestre|visa|voyage|autre
    statut: str = "idee"     # idee|planifie|en_cours|fait
    echeance: dt.date | None = None
    budget_estime: float | None = None
    notes: str | None = None
