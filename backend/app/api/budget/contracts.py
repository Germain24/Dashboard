"""Sous-routeur Budget : suivi manuel des abonnements/contrats (#362)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.budget.schemas import ContractCreate, ContractPatch
from app.services.budget import contracts as contracts_svc

router = APIRouter()


@router.get("/contracts")
def list_contracts(statut: str | None = None):
    today = date.today().isoformat()
    items = contracts_svc.list_contracts()
    if statut:
        items = [c for c in items if c.get("statut") == statut]
    return [
        {**c, "statut_echeance": contracts_svc.classify_echeance(c.get("date_echeance"), today)}
        for c in items
    ]


@router.get("/contracts/summary")
def contracts_summary():
    today = date.today().isoformat()
    items = contracts_svc.list_contracts()
    actifs = [c for c in items if c.get("statut") == "actif"]
    return {
        "cout_mensuel": contracts_svc.monthly_cost(actifs),
        "prochaines_echeances": contracts_svc.upcoming_renewals(actifs, today),
    }


@router.post("/contracts", status_code=201)
def add_contract(body: ContractCreate):
    return contracts_svc.add_contract(
        body.nom, body.categorie, body.montant, body.periodicite,
        date_echeance=body.date_echeance, notes=body.notes,
    )


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: int, body: ContractPatch):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = contracts_svc.update_contract(contract_id, patch)
    if result is None:
        raise HTTPException(404, "Contrat introuvable")
    return result


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract_id: int):
    if not contracts_svc.remove_contract(contract_id):
        raise HTTPException(404, "Contrat introuvable")
