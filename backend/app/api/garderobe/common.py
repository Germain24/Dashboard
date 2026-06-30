"""Helpers partagés entre les sous-routeurs Garde-robe (#503)."""
from __future__ import annotations

from typing import Any

from app.api.garderobe.schemas import HourlyTempOut, VetementRead, WeatherOut
from app.models.garderobe import Vetement
from app.services.garderobe import (
    is_worn_out,
    needs_wash,
    ports_avant_lavage,
    proprete_pct,
    thermal_score,
    vie_pct,
)
from app.services.garderobe.care import care_label
from app.services.garderobe.filters import season_of
from app.services.garderobe.weather import WeatherData


def vetement_to_dict(v: Vetement) -> dict[str, Any]:
    """Vetement (ORM) → dict utilisable par les services métier."""
    return {
        "id": v.id,
        "nom": v.nom,
        "marque": v.marque,
        "categorie": v.categorie,
        "sous_categorie": v.sous_categorie,
        "matiere": v.matiere,
        "couleur": v.couleur,
        "type_objectif": v.type_objectif,
        "temp_min": v.temp_min,
        "temp_max": v.temp_max,
        "etat_propre": v.etat_propre,
        "usure_max": v.usure_max,
        "portes": v.portes,
        "impermeable": v.impermeable,
        "style": v.style,
        "extra": v.extra,
    }


def vetement_to_read(v: Vetement) -> VetementRead:
    """Vetement (ORM) → VetementRead avec champs dérivés."""
    d = vetement_to_dict(v)
    return VetementRead(
        **d,
        proprete_pct=proprete_pct(d),
        vie_pct=vie_pct(d),
        needs_wash=needs_wash(d),
        is_worn_out=is_worn_out(d),
        ports_avant_lavage=ports_avant_lavage(d),
        thermal_score=thermal_score(d),
        saison=season_of(d.get("temp_min"), d.get("temp_max")),
        entretien=care_label(d.get("matiere")),
    )


def weather_to_out(w: WeatherData) -> WeatherOut:
    return WeatherOut(
        temp=w.temp,
        feels=w.feels,
        temp_min=w.temp_min,
        temp_max=w.temp_max,
        humidity=w.humidity,
        wind=w.wind,
        precip=w.precip,
        desc=w.desc,
        icon=w.icon,
        source=w.source,
        pluie=w.pluie,
        snow=w.snow,
        mean_window_temp=w.mean_window_temp,
        hour_window=[
            w.hourly[0].hour if w.hourly else 0,
            w.hourly[-1].hour if w.hourly else 0,
        ],
        hourly=[HourlyTempOut(**h.to_dict()) for h in w.hourly],
    )
