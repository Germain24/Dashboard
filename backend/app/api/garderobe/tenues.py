"""Sous-routeur Garde-robe : météo, slots, suggestion et validation de tenue (#503)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.garderobe.common import vetement_to_dict, vetement_to_read, weather_to_out
from app.api.garderobe.schemas import (
    OutfitSlotOut,
    SlotInfo,
    SlotsResponse,
    SuggestRequest,
    SuggestResponse,
    ValiderItemUpdate,
    ValiderRequest,
    ValiderResponse,
    WeatherOut,
)
from app.core.db import get_session
from app.models.garderobe import TenueHistory, Vetement
from app.services.garderobe import (
    SLOTS,
    needs_wash,
    ports_avant_lavage,
    suggest_outfit,
    vie_pct,
)
from app.services.garderobe.weather import get_weather

router = APIRouter()


@router.get("/meteo", response_model=WeatherOut)
def get_meteo(force_refresh: bool = False) -> WeatherOut:
    try:
        w = get_weather(force_refresh=force_refresh)
    except Exception as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"météo indisponible : {e}",
        ) from e
    return weather_to_out(w)


@router.get("/slots", response_model=SlotsResponse)
def list_slots() -> SlotsResponse:
    return SlotsResponse(slots=[SlotInfo(**s) for s in SLOTS])


@router.post("/suggest", response_model=SuggestResponse)
def suggest(
    payload: SuggestRequest = SuggestRequest(),
    session: Session = Depends(get_session),
) -> SuggestResponse:
    # 1) Météo
    try:
        weather = get_weather()
    except Exception as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"météo indisponible : {e}",
        ) from e

    mean_temp = payload.mean_temp if payload.mean_temp is not None else weather.mean_window_temp
    rain = payload.rain if payload.rain is not None else weather.pluie

    # 2) Wardrobe
    rows = session.exec(select(Vetement)).all()
    wardrobe = [vetement_to_dict(v) for v in rows]
    by_id = {v.id: v for v in rows}

    # 3) Optimizer
    result = suggest_outfit(wardrobe, mean_temp, rain)

    # 4) Format
    slots_out: list[OutfitSlotOut] = []
    for s in SLOTS:
        sid = s["id"]
        chosen = result.get(sid)
        if chosen and isinstance(chosen, dict) and chosen.get("id") in by_id:
            slots_out.append(OutfitSlotOut(
                slot_id=sid,
                vetement=vetement_to_read(by_id[chosen["id"]]),
            ))
        else:
            slots_out.append(OutfitSlotOut(slot_id=sid, vetement=None))

    return SuggestResponse(
        slots=slots_out,
        use_body=bool(result.get("__use_body", False)),
        target_thermal=float(result.get("__target_thermal", 0.0)),
        total_thermal=float(result.get("__total_thermal", 0.0)),
        style_score=float(result.get("__style", 0.0)),
        mean_temp=float(mean_temp),
        weather=weather_to_out(weather),
    )


@router.post("/valider", response_model=ValiderResponse)
def valider(
    payload: ValiderRequest,
    session: Session = Depends(get_session),
) -> ValiderResponse:
    # Récupère et incrémente les portes
    updates: list[ValiderItemUpdate] = []
    tenue_noms: dict[str, Optional[str]] = {}
    tenue_ids: dict[str, Optional[str]] = {}

    for slot_id, vet_id in payload.tenue.items():
        if vet_id is None:
            tenue_noms[slot_id] = None
            tenue_ids[slot_id] = None
            continue
        v = session.get(Vetement, vet_id)
        if not v:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"vetement '{vet_id}' (slot {slot_id}) introuvable",
            )
        v.portes = (v.portes or 0) + 1
        v.updated_at = dt.datetime.utcnow()
        session.add(v)
        d = vetement_to_dict(v)
        updates.append(ValiderItemUpdate(
            id=v.id,
            nom=v.nom,
            portes=v.portes,
            needs_wash=needs_wash(d),
            ports_avant_lavage=ports_avant_lavage(d),
            vie_pct=vie_pct(d),
        ))
        tenue_noms[slot_id] = v.nom
        tenue_ids[slot_id] = v.id

    # Log history
    history = TenueHistory(
        date=dt.datetime.utcnow(),
        tenue=tenue_noms,
        ids=tenue_ids,
        note=payload.note,
    )
    session.add(history)
    session.commit()
    session.refresh(history)

    return ValiderResponse(history_id=history.id, updates=updates)
