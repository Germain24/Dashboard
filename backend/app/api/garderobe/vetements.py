"""Sous-routeur Garde-robe : CRUD /vetements (#503)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import Session, select

from app.api.garderobe.common import vetement_to_dict, vetement_to_read
from app.api.garderobe.schemas import VetementCreate, VetementRead, VetementUpdate
from app.core.db import get_session
from app.models.garderobe import Vetement
from app.repositories.garderobe import VetementRepository
from app.services.garderobe import is_worn_out, needs_wash, proprete_pct
from app.services.garderobe.filters import matches_filters

router = APIRouter()


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
        d = vetement_to_dict(v)
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
        out.append(vetement_to_read(v))
    return out


@router.post("/vetements", response_model=VetementRead, status_code=status.HTTP_201_CREATED)
def create_vetement(
    payload: VetementCreate,
    session: Session = Depends(get_session),
) -> VetementRead:
    repo = VetementRepository(session)
    if repo.get(payload.id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"id '{payload.id}' déjà utilisé")
    v = repo.create(payload.model_dump())
    return vetement_to_read(v)


@router.get("/vetements/{vetement_id}", response_model=VetementRead)
def get_vetement(vetement_id: str, session: Session = Depends(get_session)) -> VetementRead:
    v = VetementRepository(session).get(vetement_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
    return vetement_to_read(v)


@router.patch("/vetements/{vetement_id}", response_model=VetementRead)
def update_vetement(
    vetement_id: str,
    payload: VetementUpdate,
    session: Session = Depends(get_session),
) -> VetementRead:
    repo = VetementRepository(session)
    v = repo.get(vetement_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
    data = payload.model_dump(exclude_unset=True)
    data["updated_at"] = dt.datetime.utcnow()
    v = repo.update(v, data)
    return vetement_to_read(v)


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
    return vetement_to_read(v)


@router.delete("/vetements/{vetement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vetement(vetement_id: str, session: Session = Depends(get_session)) -> None:
    if not VetementRepository(session).delete_by_id(vetement_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vetement '{vetement_id}' introuvable")
