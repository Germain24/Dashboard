"""Test de contrôle Alembic : le schéma issu de `upgrade head` doit correspondre
aux modèles SQLModel (un autogenerate ne doit produire aucune différence).

Garantit qu'on n'oublie pas de créer une migration après avoir modifié un modèle.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from app import models  # noqa: F401  -- enregistre toutes les tables sur metadata

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Types de diffs ignorés : SQLite ne supporte pas certaines introspections fines
# (variantes de types, defaults serveur), ce qui génère du bruit non significatif.
_IGNORED_DIFF_TYPES = {"modify_type", "modify_default", "modify_nullable"}


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migrations_match_models(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "migration_check.db"
    db_url = f"sqlite:///{db_file}"
    # env.py lit ALEMBIC_DB_URL en priorité : on cible bien la base temporaire.
    monkeypatch.setenv("ALEMBIC_DB_URL", db_url)

    # 1) Applique toutes les migrations sur une base vierge.
    command.upgrade(_alembic_config(db_url), "head")

    # 2) Compare le schéma obtenu aux modèles SQLModel.
    engine = create_engine(db_url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"render_as_batch": True, "compare_type": False}
        )
        diffs = compare_metadata(ctx, SQLModel.metadata)
    engine.dispose()

    significant = [d for d in diffs if not (isinstance(d, tuple) and d and d[0] in _IGNORED_DIFF_TYPES)]
    assert not significant, (
        "Le schéma des migrations diffère des modèles — créez une migration "
        f"(`alembic revision --autogenerate`). Diffs : {significant}"
    )
