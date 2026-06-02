"""Couche repository générique — découple les services de SQLModel.

Chaque module expose des repositories (voir ``app/repositories/``) qui héritent
de :class:`Repository`. Les services parlent au repository plutôt que de
manipuler directement ``Session`` + ``select`` : le jour où la persistance
change (autre ORM, Postgres, cache), seul le repository bouge.

Exemple ::

    from app.core.repository import Repository
    from app.models.finance import Transaction

    class TransactionRepository(Repository[Transaction]):
        model = Transaction

    repo = TransactionRepository(session)
    tx = repo.get(1)
    repo.delete(tx)
"""

from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, TypeVar

from sqlmodel import Session, SQLModel, select

ModelT = TypeVar("ModelT", bound=SQLModel)


class Repository(Generic[ModelT]):
    """Repository CRUD générique sur un modèle SQLModel.

    Sous-classer en fixant l'attribut de classe ``model``.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Lecture ────────────────────────────────────────────────────────────
    def get(self, obj_id: Any) -> Optional[ModelT]:
        return self.session.get(self.model, obj_id)

    def list(
        self,
        *,
        offset: int = 0,
        limit: Optional[int] = None,
        order_by: Any = None,
        **filters: Any,
    ) -> list[ModelT]:
        q = select(self.model)
        for field, value in filters.items():
            q = q.where(getattr(self.model, field) == value)
        if order_by is not None:
            q = q.order_by(order_by)
        if offset:
            q = q.offset(offset)
        if limit is not None:
            q = q.limit(limit)
        return list(self.session.exec(q).all())

    def count(self, **filters: Any) -> int:
        q = select(self.model)
        for field, value in filters.items():
            q = q.where(getattr(self.model, field) == value)
        return len(list(self.session.exec(q).all()))

    # ── Écriture ──────────────────────────────────────────────────────────
    def add(self, obj: ModelT, *, commit: bool = True) -> ModelT:
        self.session.add(obj)
        if commit:
            self.session.commit()
            self.session.refresh(obj)
        return obj

    def create(self, data: dict[str, Any], *, commit: bool = True) -> ModelT:
        return self.add(self.model(**data), commit=commit)

    def update(self, obj: ModelT, data: dict[str, Any], *, commit: bool = True) -> ModelT:
        for field, value in data.items():
            setattr(obj, field, value)
        return self.add(obj, commit=commit)

    def delete(self, obj: ModelT, *, commit: bool = True) -> None:
        self.session.delete(obj)
        if commit:
            self.session.commit()

    def delete_by_id(self, obj_id: Any, *, commit: bool = True) -> bool:
        obj = self.get(obj_id)
        if obj is None:
            return False
        self.delete(obj, commit=commit)
        return True

    # ── Bas niveau (échappatoire pour les requêtes complexes) ───────────────
    def exec(self, statement) -> Sequence[Any]:
        return self.session.exec(statement).all()
