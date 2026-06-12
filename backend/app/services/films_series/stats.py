"""Stats visionnage (#539) — fonctions pures."""

from __future__ import annotations

import datetime as dt

from app.models.films_series import WatchItem


def watchlist_stats_pure(items: list[WatchItem], year: int | None = None) -> dict:
    """Calcule les statistiques de visionnage depuis une liste d'items."""
    if year is None:
        year = dt.date.today().year

    films = [i for i in items if i.type == "film"]
    series = [i for i in items if i.type == "serie"]
    vus = [i for i in items if i.statut == "vu"]
    vus_films = [i for i in films if i.statut == "vu"]
    vus_series = [i for i in series if i.statut == "vu"]
    vus_annee = [
        i for i in vus if i.date_vue is not None and i.date_vue.year == year
    ]

    temps_films = sum((i.duree_min or 90) for i in vus_films)
    temps_series = sum((i.nb_episodes_total or 10) * 45 for i in vus_series)
    temps_total_min = temps_films + temps_series

    return {
        "films_total": len(films),
        "series_total": len(series),
        "films_vus": len(vus_films),
        "series_vues": len(vus_series),
        "vus_annee": len(vus_annee),
        "temps_estime_heures": round(temps_total_min / 60, 1),
        "annee": year,
    }
