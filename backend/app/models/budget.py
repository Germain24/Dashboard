import datetime as dt

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.timeutil import utcnow


class BudgetCategory(SQLModel, table=True):
    __tablename__ = "budget_category"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    parent_id: int | None = Field(default=None, foreign_key="budget_category.id")
    couleur: str = "#6366f1"


class BudgetRule(SQLModel, table=True):
    __tablename__ = "budget_rule"
    id: int | None = Field(default=None, primary_key=True)
    pattern: str
    category_id: int = Field(foreign_key="budget_category.id")
    priorite: int = 0
    created_at: dt.datetime = Field(default_factory=utcnow)


class BudgetTransaction(SQLModel, table=True):
    __tablename__ = "budget_transaction"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date
    montant: float
    marchand: str = ""
    description: str = ""
    category_id: int | None = Field(default=None, foreign_key="budget_category.id")
    compte: str = "principal"
    devise: str = "CAD"
    auto: bool = False
    tags: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: dt.datetime = Field(default_factory=utcnow)
    # Nullable so historic/manual transactions remain untouched. Imported rows
    # receive a deterministic fingerprint protected by a unique index.
    import_source: str | None = Field(default=None, max_length=40)
    import_external_id: str | None = Field(default=None, max_length=255)
    import_fingerprint: str | None = Field(default=None, max_length=64, unique=True, index=True)


class BudgetEnvelope(SQLModel, table=True):
    __tablename__ = "budget_envelope"
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="budget_category.id")
    mois: str
    montant: float
    __table_args__ = (UniqueConstraint("category_id", "mois"),)
