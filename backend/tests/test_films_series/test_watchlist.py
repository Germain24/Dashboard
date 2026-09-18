"""Tests CRUD watchlist + stats (#536, #539, #540)."""

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.models.films_series import WatchItem
from app.services.films_series.stats import watchlist_stats_pure
from app.services.films_series.watchlist import (
    create_watch_item,
    delete_watch_item,
    get_serie_progress,
    get_watchlist,
    update_watch_item,
    upsert_serie_progress,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ─── CRUD ──────────────────────────────────────────────────────────────────


def test_create_and_list(session):
    create_watch_item(session, titre="Inception", type="film")
    create_watch_item(session, titre="Breaking Bad", type="serie")
    all_items = get_watchlist(session)
    assert len(all_items) == 2


def test_filter_by_type(session):
    create_watch_item(session, titre="Inception", type="film")
    create_watch_item(session, titre="Breaking Bad", type="serie")
    films = get_watchlist(session, type="film")
    series = get_watchlist(session, type="serie")
    assert len(films) == 1
    assert len(series) == 1
    assert films[0].titre == "Inception"


def test_filter_by_statut(session):
    create_watch_item(session, titre="Inception", type="film", statut="vu")
    create_watch_item(session, titre="Avatar", type="film", statut="a_voir")
    vus = get_watchlist(session, statut="vu")
    assert len(vus) == 1
    assert vus[0].titre == "Inception"


def test_update(session):
    item = create_watch_item(session, titre="Inception", type="film", statut="a_voir")
    updated = update_watch_item(session, item.id, {"statut": "vu", "note": 4.5})
    assert updated.statut == "vu"
    assert updated.note == 4.5


def test_update_not_found(session):
    assert update_watch_item(session, 9999, {"statut": "vu"}) is None


def test_delete(session):
    item = create_watch_item(session, titre="Avatar", type="film")
    assert delete_watch_item(session, item.id) is True
    assert get_watchlist(session) == []


def test_delete_not_found(session):
    assert delete_watch_item(session, 9999) is False


def test_genres_serialized_as_json(session):
    item = create_watch_item(session, titre="Inception", type="film", genres=["Action", "SF"])
    assert '"Action"' in item.genres
    assert '"SF"' in item.genres


# ─── Progression séries ──────────────────────────────────────────────────


def test_upsert_progress(session):
    serie = create_watch_item(session, titre="Breaking Bad", type="serie")
    prog = upsert_serie_progress(session, serie.id, saison=2, episode_courant=7, episodes_saison=13)
    assert prog.saison == 2
    assert prog.episode_courant == 7


def test_upsert_progress_updates_existing(session):
    serie = create_watch_item(session, titre="The Office", type="serie")
    upsert_serie_progress(session, serie.id, saison=1, episode_courant=3)
    prog2 = upsert_serie_progress(session, serie.id, saison=1, episode_courant=6)
    assert prog2.episode_courant == 6
    all_progs = get_serie_progress(session, serie.id)
    assert all_progs is not None


def test_delete_cascades_progress(session):
    serie = create_watch_item(session, titre="GoT", type="serie")
    upsert_serie_progress(session, serie.id, saison=1, episode_courant=1)
    delete_watch_item(session, serie.id)
    assert get_serie_progress(session, serie.id) is None


# ─── Mode manuel sans TMDB (#540) ───────────────────────────────────────


def test_manual_add_without_tmdb(session):
    """Un item ajouté manuellement (sans tmdb_id) doit fonctionner complètement."""
    item = create_watch_item(
        session,
        titre="Mon film perso",
        type="film",
        annee=2023,
        note=3.5,
        genres=["Comédie"],
    )
    assert item.id is not None
    assert item.tmdb_id is None
    updated = update_watch_item(session, item.id, {"statut": "vu", "date_vue": dt.date(2026, 6, 11)})
    assert updated.statut == "vu"
    assert updated.date_vue == dt.date(2026, 6, 11)


def test_manual_serie_without_tmdb(session):
    serie = create_watch_item(
        session,
        titre="Série inconnue",
        type="serie",
        nb_saisons=3,
        nb_episodes_total=30,
    )
    assert serie.tmdb_id is None
    upsert_serie_progress(session, serie.id, saison=2, episode_courant=5)
    prog = get_serie_progress(session, serie.id)
    assert prog.saison == 2


# ─── Stats (#539) ───────────────────────────────────────────────────────


def _item(**kw) -> WatchItem:
    base = dict(id=None, titre="T", type="film", statut="a_voir")
    base.update(kw)
    return WatchItem(**base)


def test_stats_empty():
    s = watchlist_stats_pure([])
    assert s["films_total"] == 0
    assert s["temps_estime_heures"] == 0.0


def test_stats_counts_types():
    items = [
        _item(type="film", statut="vu", duree_min=120, date_vue=dt.date(2026, 3, 1)),
        _item(type="film", statut="a_voir"),
        _item(type="serie", statut="vu", nb_episodes_total=20, date_vue=dt.date(2026, 4, 1)),
    ]
    s = watchlist_stats_pure(items, year=2026)
    assert s["films_total"] == 2
    assert s["series_total"] == 1
    assert s["films_vus"] == 1
    assert s["series_vues"] == 1
    assert s["vus_annee"] == 2


def test_stats_temps_estime():
    items = [
        _item(type="film", statut="vu", duree_min=120),
        _item(type="serie", statut="vu", nb_episodes_total=10),  # 10 * 45 = 450 min
    ]
    s = watchlist_stats_pure(items)
    expected_hours = round((120 + 450) / 60, 1)
    assert s["temps_estime_heures"] == expected_hours


def test_stats_vus_annee_filter():
    items = [
        _item(type="film", statut="vu", date_vue=dt.date(2026, 1, 1)),
        _item(type="film", statut="vu", date_vue=dt.date(2025, 12, 31)),  # autre année
        _item(type="film", statut="vu", date_vue=None),                   # pas de date
    ]
    s = watchlist_stats_pure(items, year=2026)
    assert s["vus_annee"] == 1
