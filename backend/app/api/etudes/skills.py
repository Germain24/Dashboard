"""Sous-routeur Études : suivi de compétences (skill tree, #352)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class _SkillIn(BaseModel):
    nom: str
    categorie: str
    niveau: int = 1


class _SkillPatch(BaseModel):
    nom: Optional[str] = None
    categorie: Optional[str] = None
    niveau: Optional[int] = None


class _PreuveIn(BaseModel):
    texte: str
    date: Optional[str] = None


@router.get("/skills")
def skills_list():
    from app.services.etudes import skills as skills_svc
    return skills_svc.list_skills()


@router.get("/skills/stats")
def skills_stats():
    from app.services.etudes import skills as skills_svc
    all_skills = skills_svc.list_skills()
    return {
        "par_categorie": skills_svc.skills_by_category(all_skills),
        "global": skills_svc.overall_stats(all_skills),
    }


@router.post("/skills", status_code=201)
def skills_add(body: _SkillIn):
    from app.services.etudes import skills as skills_svc
    try:
        return skills_svc.add_skill(body.nom, body.categorie, body.niveau)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.patch("/skills/{skill_id}")
def skills_update(skill_id: int, body: _SkillPatch):
    from app.services.etudes import skills as skills_svc
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        result = skills_svc.update_skill(skill_id, patch)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if result is None:
        raise HTTPException(404, "Compétence introuvable")
    return result


@router.delete("/skills/{skill_id}", status_code=204)
def skills_delete(skill_id: int):
    from app.services.etudes import skills as skills_svc
    if not skills_svc.remove_skill(skill_id):
        raise HTTPException(404, "Compétence introuvable")


@router.post("/skills/{skill_id}/preuves")
def skills_add_preuve(skill_id: int, body: _PreuveIn):
    from app.services.etudes import skills as skills_svc
    result = skills_svc.add_preuve(skill_id, body.texte, date=body.date)
    if result is None:
        raise HTTPException(404, "Compétence introuvable")
    return result
