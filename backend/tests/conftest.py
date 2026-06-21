"""Fixtures de test partagées entre modules (#188).

Fournit une base SQLite en mémoire prête à l'emploi et un moyen de remplacer
l'engine global de l'app (pour tester le scheduler / les jobs qui ouvrent leur
propre Session).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  — enregistre toutes les tables sur SQLModel.metadata


@pytest.fixture(autouse=True)
def _disable_adonis_scrape(monkeypatch):
    """Garde-fou : la re-tarification Adonis peut lancer un scraper navigateur
    (subprocess) au lancement de l'optimisation nutrition. Aucun test ne doit
    déclencher navigateur/réseau → on la désactive partout. Le code de prod
    reste actif par défaut (variable absente → activé)."""
    monkeypatch.setenv("ADONIS_PRODUCE_PRICING", "0")


@pytest.fixture
def mem_engine():
    """Engine SQLite en mémoire avec toutes les tables créées."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def mem_session(mem_engine):
    """Session ouverte sur la base en mémoire."""
    with Session(mem_engine) as session:
        yield session


@pytest.fixture
def patched_db_engine(mem_engine, monkeypatch):
    """Remplace `app.core.db.engine` par l'engine en mémoire.

    Utile pour les fonctions qui font `from app.core.db import engine` en interne
    (ex. `run_job`). Retourne l'engine pour relire la base dans le test.
    """
    import app.core.db as db

    monkeypatch.setattr(db, "engine", mem_engine)
    return mem_engine
