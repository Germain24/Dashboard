"""Tests modèles WatchItem + SerieProgress (#534)."""

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.films_series import SerieProgress, WatchItem


@pytest.fixture
def engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    yield e
    SQLModel.metadata.drop_all(e)


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


def test_watch_item_default_values():
    item = WatchItem(titre="Inception")
    assert item.type == "film"
    assert item.statut == "a_voir"
    assert item.genres == "[]"
    assert item.synopsis == ""


def test_watch_item_persist(session):
    item = WatchItem(titre="Inception", type="film", annee=2010, tmdb_id=27205)
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.id is not None
    found = session.exec(select(WatchItem).where(WatchItem.tmdb_id == 27205)).first()
    assert found is not None
    assert found.titre == "Inception"


def test_serie_progress_persist(session):
    serie = WatchItem(titre="Breaking Bad", type="serie", nb_saisons=5, nb_episodes_total=62)
    session.add(serie)
    session.commit()
    session.refresh(serie)

    prog = SerieProgress(watch_item_id=serie.id, saison=2, episode_courant=7, episodes_saison=13)
    session.add(prog)
    session.commit()
    session.refresh(prog)

    assert prog.id is not None
    assert prog.saison == 2
    assert prog.episode_courant == 7
    found = session.exec(
        select(SerieProgress).where(SerieProgress.watch_item_id == serie.id)
    ).first()
    assert found is not None


def test_watch_item_fields():
    item = WatchItem(
        titre="The Crown",
        type="serie",
        tmdb_id=65494,
        statut="en_cours",
        note=4.5,
        annee=2016,
        genres='["Drame", "Histoire"]',
        poster_url="https://example.com/poster.jpg",
        nb_saisons=6,
        nb_episodes_total=60,
        synopsis="La vie de la famille royale britannique.",
        date_vue=dt.date(2026, 1, 15),
    )
    assert item.nb_saisons == 6
    assert item.date_vue == dt.date(2026, 1, 15)
    assert item.note == 4.5
