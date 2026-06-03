"""Endpoints du module Garde-robe — CONV 2.

Endpoints exposés (préfixe `/garderobe`) :
- GET    /vetements              liste avec filtres
- POST   /vetements              création
- GET    /vetements/{id}         détail
- PATCH  /vetements/{id}         édition partielle
- DELETE /vetements/{id}
- GET    /meteo                  météo (cachée 30 min)
- GET    /slots                  config des 12 slots (pour le front)
- POST   /suggest                suggère une tenue (body coton inclus)
- POST   /valider                valide une tenue : portes +1, log history
- GET    /history                historique des tenues
- GET    /stats                  distribution & "à laver"
- GET    /recommendations        suggestions d'achat
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import Session, select

from app.api.schemas_garderobe import (
    CountEntry,
    HourlyTempOut,
    OutfitSlotOut,
    PlannerDayUpdate,
    RecommendationOut,
    SlotInfo,
    SlotsResponse,
    StatsResponse,
    SuggestRequest,
    SuggestResponse,
    TenueHistoryOut,
    ValiderItemUpdate,
    ValiderRequest,
    ValiderResponse,
    VetementCreate,
    VetementRead,
    VetementUpdate,
    WeatherOut,
)
from app.core.db import get_session
from app.models.garderobe import TenueHistory, Vetement
from app.services.garderobe import (
    EMO_CAT,
    SLOTS,
    calculate_thermal_gap,
    get_purchase_recommendations,
    is_worn_out,
    needs_wash,
    ports_avant_lavage,
    proprete_pct,
    style_score,
    suggest_outfit,
    thermal_score,
    vie_pct,
)
from app.services.garderobe.care import care_label
from app.services.garderobe.filters import matches_filters, season_of
from app.services.garderobe.frequency import wear_buckets
from app.services.garderobe.style import get_color_category
from app.services.garderobe.weather import WeatherData, get_weather

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _vetement_to_dict(v: Vetement) -> dict[str, Any]:
    """Vetement (ORM) → dict utilisable par les services métier."""
    return {
        "id": v.id,
        "nom": v.nom,
        "marque": v.marque,
        "categorie": v.categorie,
        "sous_categorie": v.sous_categorie,
        "matiere": v.matiere,
        "couleur": v.couleur,
        "temp_min": v.temp_min,
        "temp_max": v.temp_max,
        "etat_propre": v.etat_propre,
        "usure_max": v.usure_max,
        "portes": v.portes,
        "impermeable": v.impermeable,
        "style": v.style,
        "extra": v.extra,
    }


def _vetement_to_read(v: Vetement) -> VetementRead:
    """Vetement (ORM) → VetementRead avec champs dérivés."""
    d = _vetement_to_dict(v)
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


def _weather_to_out(w: WeatherData) -> WeatherOut:
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


# ─────────────────────────────────────────────────────────────────────────────
# /vetements — CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/vetements", response_model=list[VetementRead])
def list_vetements(
    categorie: Optional[str] = None,
    style: Optional[str] = None,
    couleur: Optional[str] = Query(None, description="Filtre couleur exacte (insensible à la casse)"),
    saison: Optional[str] = Query(None, description="Filtre saison : hiver, mi-saison, été"),
    occasion: Optional[str] = Query(None, description="Filtre occasion (style ou extra.occasion)"),
    etat: Optional[str] = Query(
        None,
        description="Filtre d'état : propre, mi-sale, a-laver, hs",
    ),
    session: Session = Depends(get_session),
) -> list[VetementRead]:
    stmt = select(Vetement)
    if categorie:
        stmt = stmt.where(Vetement.categorie == categorie)
    vetements = session.exec(stmt).all()

    out: list[VetementRead] = []
    for v in vetements:
        d = _vetement_to_dict(v)
        # Filtre style (multi-styles supporté)
        if style:
            s = v.style or []
            styles_list = s if isinstance(s, list) else ([s] if s else [])
            if style not in styles_list:
                continue
        # Filtres saison / couleur / occasion (#78)
        if not matches_filters(d, couleur=couleur, saison=saison, occasion=occasion):
            continue
        # Filtre état
        if etat:
            p = proprete_pct(d)
            if etat == "propre" and not (p >= 70 and not needs_wash(d)):
                continue
            if etat == "mi-sale" and not (30 <= p < 70):
                continue
            if etat == "a-laver" and not needs_wash(d):
                continue
            if etat == "hs" and not is_worn_out(d):
                continue
        out.append(_vetement_to_read(v))
    return out


@router.post("/vetements", response_model=VetementRead, status_code=status.HTTP_201_CREATED)
def create_vetement(
    payload: VetementCreate,
    session: Session = Depends(get_session),
) -> VetementRead:
    existing = session.get(Vetement, payload.id)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"id '{payload.id}' déjà utilisé")
    v = Vetement(**payload.model_dump())
    session.add(v)
    session.commit()
    session.refresh(v)
    return _vetement_to_read(v)


@router.get("/vetements/{vetement_id}", response_model=VetementRead)
def get_vetement(vetement_id: str, session: Session = Depends(get_session)) -> VetementRead:
    v = session.get(Vetement, vetement_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
    return _vetement_to_read(v)


@router.patch("/vetements/{vetement_id}", response_model=VetementRead)
def update_vetement(
    vetement_id: str,
    payload: VetementUpdate,
    session: Session = Depends(get_session),
) -> VetementRead:
    v = session.get(Vetement, vetement_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(v, key, val)
    v.updated_at = dt.datetime.utcnow()
    session.add(v)
    session.commit()
    session.refresh(v)
    return _vetement_to_read(v)


@router.post("/vetements/{vetement_id}/photo", response_model=VetementRead)
async def upload_vetement_photo(
    vetement_id: str,
    file: UploadFile = File(...),
    couleur_dominante: Optional[str] = None,
    session: Session = Depends(get_session),
) -> VetementRead:
    """Téléverse une photo pour un vêtement + couleur dominante détectée (#75)."""
    from app.services.garderobe.photos import save_vetement_photo

    content = await file.read()
    try:
        v = save_vetement_photo(
            session, vetement_id, file.filename or "photo.jpg", content,
            couleur_dominante=couleur_dominante,
        )
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return _vetement_to_read(v)


@router.delete("/vetements/{vetement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vetement(vetement_id: str, session: Session = Depends(get_session)) -> None:
    v = session.get(Vetement, vetement_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
    session.delete(v)
    session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# /meteo
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/meteo", response_model=WeatherOut)
def get_meteo(force_refresh: bool = False) -> WeatherOut:
    try:
        w = get_weather(force_refresh=force_refresh)
    except Exception as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"météo indisponible : {e}",
        ) from e
    return _weather_to_out(w)


# ─────────────────────────────────────────────────────────────────────────────
# /slots
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/slots", response_model=SlotsResponse)
def list_slots() -> SlotsResponse:
    return SlotsResponse(slots=[SlotInfo(**s) for s in SLOTS])


# ─────────────────────────────────────────────────────────────────────────────
# /suggest
# ─────────────────────────────────────────────────────────────────────────────

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
    wardrobe = [_vetement_to_dict(v) for v in rows]
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
                vetement=_vetement_to_read(by_id[chosen["id"]]),
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
        weather=_weather_to_out(weather),
    )


# ─────────────────────────────────────────────────────────────────────────────
# /valider
# ─────────────────────────────────────────────────────────────────────────────

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
        d = _vetement_to_dict(v)
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


# ─────────────────────────────────────────────────────────────────────────────
# /history
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[TenueHistoryOut])
def history(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[TenueHistoryOut]:
    stmt = select(TenueHistory).order_by(TenueHistory.date.desc()).limit(limit)
    return [
        TenueHistoryOut(id=h.id, date=h.date, tenue=h.tenue, ids=h.ids, note=h.note)
        for h in session.exec(stmt).all()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    rows = session.exec(select(Vetement)).all()
    items = [_vetement_to_dict(v) for v in rows]
    total = len(items)

    def _count(field: str) -> list[CountEntry]:
        counts: dict[str, int] = {}
        for it in items:
            v = it.get(field)
            if isinstance(v, list):
                for x in v:
                    if x:
                        counts[x] = counts.get(x, 0) + 1
            elif v:
                counts[v] = counts.get(v, 0) + 1
        return [
            CountEntry(label=label, count=count)
            for label, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

    # Ratio couleurs
    cats_count = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
    for it in items:
        cats_count[get_color_category(it.get("couleur"))] += 1
    denom = sum(cats_count.values()) or 1
    color_ratio = {k: v / denom for k, v in cats_count.items()}

    a_laver_rows = [_vetement_to_read(v) for v in rows if needs_wash(_vetement_to_dict(v))]
    hs_rows = [_vetement_to_read(v) for v in rows if is_worn_out(_vetement_to_dict(v))]

    # Valeur estimée : somme des prix renseignés dans extra.prix (#80)
    valeur = 0.0
    valeur_count = 0
    for it in items:
        prix = (it.get("extra") or {}).get("prix")
        if isinstance(prix, (int, float)) and prix > 0:
            valeur += float(prix)
            valeur_count += 1

    return StatsResponse(
        total=total,
        par_categorie=_count("categorie"),
        par_couleur=_count("couleur"),
        par_style=_count("style"),
        a_laver=a_laver_rows,
        hs=hs_rows,
        color_ratio=color_ratio,
        valeur_estimee=round(valeur, 2),
        valeur_count=valeur_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /recommendations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/frequence")
def frequence(top_n: int = Query(5, ge=1, le=20), session: Session = Depends(get_session)) -> dict:
    """Fréquence de port : jamais portées (à recycler), moins / plus portées (#77)."""
    rows = list(session.exec(select(Vetement)).all())
    by_id = {v.id: v for v in rows}
    buckets = wear_buckets([_vetement_to_dict(v) for v in rows], top_n=top_n)

    def resolve(ids: list[str]) -> list[VetementRead]:
        return [_vetement_to_read(by_id[i]) for i in ids if i in by_id]

    return {
        "total": buckets["total"],
        "never_worn_count": buckets["never_worn_count"],
        "never_worn": resolve(buckets["never_worn"]),
        "least_worn": resolve(buckets["least_worn"]),
        "most_worn": resolve(buckets["most_worn"]),
    }


@router.get("/planner")
def get_planner(start: Optional[dt.date] = None, session: Session = Depends(get_session)) -> dict:
    """Plan de tenues de la semaine + événements d'agenda par jour (#79).

    `start` = premier jour (par défaut le lundi de la semaine courante).
    """
    from app.services.agenda.events import list_events_for_window
    from app.services.garderobe.planner import get_day, monday_of, week_dates

    start = monday_of(start or dt.date.today())
    rows = list(session.exec(select(Vetement)).all())
    by_id = {v.id: v for v in rows}

    days = []
    for d in week_dates(start):
        tenue_ids = get_day(d)
        tenue = {
            slot: (_vetement_to_read(by_id[vid]) if vid in by_id else None)
            for slot, vid in tenue_ids.items()
        }
        # Lien agenda : événements du jour (titre + catégorie)
        day_start = dt.datetime.combine(d, dt.time.min)
        day_end = day_start + dt.timedelta(days=1)
        try:
            evs = list_events_for_window(session, day_start, day_end)
            events = [{"titre": e.titre, "categorie": e.categorie, "heure": e.debut.strftime("%H:%M")} for e in evs]
        except Exception:  # pragma: no cover — défensif si agenda indispo
            events = []
        days.append({"date": str(d), "weekday": d.weekday(), "tenue": tenue, "events": events})

    return {"start": str(start), "days": days}


@router.put("/planner/{date}")
def set_planner_day(date: dt.date, payload: PlannerDayUpdate, session: Session = Depends(get_session)) -> dict:
    """Enregistre la tenue planifiée d'un jour (#79)."""
    from app.services.garderobe.planner import set_day

    rows = session.exec(select(Vetement)).all()
    by_id = {v.id: v for v in rows}
    cleaned = set_day(date, payload.tenue)
    tenue = {
        slot: (_vetement_to_read(by_id[vid]) if vid in by_id else None)
        for slot, vid in cleaned.items()
    }
    return {"date": str(date), "tenue": tenue}


@router.get("/recommendations", response_model=list[RecommendationOut])
def recommendations(session: Session = Depends(get_session)) -> list[RecommendationOut]:
    items = [_vetement_to_dict(v) for v in session.exec(select(Vetement)).all()]
    recs = get_purchase_recommendations(items)
    return [RecommendationOut(**r) for r in recs]
