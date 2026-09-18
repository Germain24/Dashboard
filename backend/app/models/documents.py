"""Module Documents/Administratif (#548)."""
import datetime as dt
from app.core.timeutil import utcnow

from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    __tablename__ = "document"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    type: str = "autre"       # cnI | passeport | contrat | garantie | assurance | fiscal | medical | autre
    notes: str = ""
    date_expiration: dt.date | None = None
    date_emission: dt.date | None = None
    organisme: str = ""       # mairie, banque, assureur…
    fichier_url: str | None = None  # chemin local ou URL
    tags: str = "[]"          # JSON list
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime = Field(default_factory=utcnow)
