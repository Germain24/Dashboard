"""Seeds de démo réalistes (#178) pour tester l'UI sans données perso.

Insère un petit jeu de données cohérent réparti sur plusieurs modules. Marque
chaque enregistrement (source/auto) quand le modèle le permet, pour pouvoir les
retrouver/supprimer facilement.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select


def seed_demo(session: Session) -> dict[str, int]:
    """Insère des données de démo. Retourne le nombre d'enregistrements par module."""
    today = dt.date.today()
    counts: dict[str, int] = {}

    # Budget : quelques transactions du mois
    from app.models.budget import BudgetTransaction
    budget_rows = [
        BudgetTransaction(date=today, montant=2200.0, marchand="Salaire", auto=True),
        BudgetTransaction(date=today - dt.timedelta(days=1), montant=-58.40, marchand="Épicerie Metro", auto=True),
        BudgetTransaction(date=today - dt.timedelta(days=2), montant=-14.99, marchand="Spotify", auto=True),
        BudgetTransaction(date=today - dt.timedelta(days=3), montant=-42.0, marchand="Restaurant", auto=True),
    ]
    for r in budget_rows:
        session.add(r)
    counts["budget"] = len(budget_rows)

    # Habitudes : 3 habitudes + complétions du jour
    from app.models.habitudes import Habit, HabitEntry
    habits = [Habit(nom="Méditation", icone="🧘"), Habit(nom="Sport", icone="💪"),
              Habit(nom="Lecture", icone="📖", type="quantifiable", cible=30)]
    for h in habits:
        session.add(h)
    session.commit()
    for h in habits[:2]:
        session.add(HabitEntry(habit_id=h.id, date=today, valeur=1.0))
    counts["habitudes"] = len(habits)

    # Livres
    from app.models.livres import Book
    books = [
        Book(titre="Sapiens", auteur="Y. N. Harari", statut="lu", genre="Essai", pages=443,
             note=5, date_fin=today - dt.timedelta(days=10)),
        Book(titre="Clean Code", auteur="R. C. Martin", statut="en_cours", genre="Informatique",
             pages=464, page_courante=120),
        Book(titre="Dune", auteur="F. Herbert", statut="a_lire", genre="SF", pages=688),
    ]
    for b in books:
        session.add(b)
    counts["livres"] = len(books)

    # Agenda : un événement aujourd'hui + une tâche
    from app.models.agenda import Evenement, Tache
    session.add(Evenement(
        titre="Démo : réunion", debut=dt.datetime.combine(today, dt.time(14, 0)),
        fin=dt.datetime.combine(today, dt.time(15, 0)), source="demo",
    ))
    session.add(Tache(titre="Démo : préparer le rapport", deadline=today, priorite=2))
    counts["agenda"] = 2

    session.commit()
    return counts


def has_any_data(session: Session) -> bool:
    """True si des données existent déjà (pour éviter d'écraser/dupliquer)."""
    from app.models.budget import BudgetTransaction
    from app.models.habitudes import Habit
    from app.models.livres import Book
    for cls in (BudgetTransaction, Habit, Book):
        if session.exec(select(cls)).first():
            return True
    return False
