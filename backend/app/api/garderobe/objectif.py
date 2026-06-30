"""Sous-routeur Garde-robe : onglet « Objectif » (#garderobe-objectif).

Master = data/imports/Vetements.xlsx. POST /objectif/sync l'importe dans la table
cache `objectif_type` ; GET /objectif la croise avec les vêtements possédés.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.garderobe.schemas import Emplacement, NonRattacheOut, ObjectifResponse, ObjectifTypeOut
from app.core.config import settings
from app.core.db import get_session
from app.models.garderobe import ObjectifType, Vetement
from app.services.garderobe.objectif import fill_slots
from app.services.garderobe.objectif_import import sync_objectif

router = APIRouter()


def _objectif_xlsx_path() -> Path:
    return settings.imports_dir / "Vetements.xlsx"


@router.get("/objectif", response_model=ObjectifResponse)
def get_objectif(session: Session = Depends(get_session)) -> ObjectifResponse:
    types = session.exec(select(ObjectifType).order_by(ObjectifType.ordre)).all()
    vets = session.exec(
        select(Vetement).where(Vetement.type_objectif.is_not(None))
    ).all()

    owned_by_type: dict[str, list[dict]] = {}
    for v in vets:
        owned_by_type.setdefault(v.type_objectif, []).append(
            {"id": v.id, "nom": v.nom, "marque": v.marque, "image": v.image}
        )

    type_names = {t.nom for t in types}
    non_rattaches_items = [
        NonRattacheOut(vetement_id=v.id, vetement_nom=v.nom, type_objectif=v.type_objectif)
        for v in vets
        if v.type_objectif not in type_names
    ]

    out_types: list[ObjectifTypeOut] = []
    total_emp = 0
    total_remplis = 0
    for t in types:
        res = fill_slots(t.echelle or [], t.quantite_objectif, owned_by_type.get(t.nom, []))
        total_emp += t.quantite_objectif
        total_remplis += res["rempli"]
        out_types.append(
            ObjectifTypeOut(
                nom=t.nom,
                ordre=t.ordre,
                quantite_objectif=t.quantite_objectif,
                echelle=t.echelle or [],
                rempli=res["rempli"],
                emplacements=[Emplacement(**e) for e in res["emplacements"]],
                excedent=[Emplacement(**e) for e in res["excedent"]],
            )
        )

    return ObjectifResponse(
        total_emplacements=total_emp,
        total_remplis=total_remplis,
        non_rattaches=len(non_rattaches_items),
        non_rattaches_items=non_rattaches_items,
        types=out_types,
    )


@router.post("/objectif/sync")
def post_objectif_sync(session: Session = Depends(get_session)) -> dict:
    path = _objectif_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    n = sync_objectif(session, path)
    return {"types": n}
