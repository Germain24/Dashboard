from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from app.models.budget import BudgetCategory

DEFAULT_CATEGORIES = [
    ("Logement", None), ("Loyer", "Logement"), ("Électricité", "Logement"), ("Internet", "Logement"),
    ("Transport", None), ("Essence", "Transport"), ("Transport en commun", "Transport"),
    ("Nourriture", None), ("Épicerie", "Nourriture"), ("Restaurants", "Nourriture"),
    ("Santé", None), ("Pharmacie", "Santé"), ("Sport", "Santé"),
    ("Loisirs", None), ("Cinéma", "Loisirs"), ("Sorties", "Loisirs"),
    ("Abonnements", None), ("Streaming", "Abonnements"),
    ("Revenus", None), ("Salaire", "Revenus"),
]


def seed_categories(session: Session) -> None:
    existing = {c.nom: c for c in session.exec(select(BudgetCategory)).all()}
    for nom, parent_nom in DEFAULT_CATEGORIES:
        if nom in existing:
            continue
        parent_id = existing[parent_nom].id if parent_nom and parent_nom in existing else None
        cat = BudgetCategory(nom=nom, parent_id=parent_id)
        try:
            session.add(cat)
            session.commit()
            session.refresh(cat)
            existing[nom] = cat
        except IntegrityError:
            session.rollback()
            existing[nom] = session.exec(select(BudgetCategory).where(BudgetCategory.nom == nom)).first()


def get_categories(session: Session) -> list[BudgetCategory]:
    return session.exec(select(BudgetCategory)).all()


def create_category(session: Session, nom: str, parent_id: int | None = None, couleur: str = "#6366f1") -> BudgetCategory:
    cat = BudgetCategory(nom=nom, parent_id=parent_id, couleur=couleur)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
