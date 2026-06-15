"""Routes Routines, Snapshot, Wellbeing, Templates (#201, 206, 212, 222)."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.automatisations.engine import (
    create_routine,
    delete_routine,
    execute_routine,
    get_routine,
    get_routine_runs,
    get_routines,
    rerun_run,
    rollback_run,
    trigger_webhook,
    update_routine,
)
from app.services.settings import get_preferences, set_preferences
from app.services.automatisations.snapshot import (
    build_daily_snapshot,
    get_recent_snapshots,
    get_snapshot,
    save_snapshot,
)
from app.services.automatisations.templates import get_template, get_templates
from app.services.automatisations.wellbeing import compute_wellbeing_score

router = APIRouter()


class RoutineCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "cron"
    trigger_value: str = ""
    actions: list[dict] = []
    enabled: bool = True


class RoutinePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    trigger_value: str | None = None
    actions: list[dict] | None = None
    enabled: bool | None = None


def _out(r) -> dict:
    import json
    d = r.model_dump()
    d["actions"] = json.loads(r.actions)
    return d


@router.get("/routines")
def list_routines(session: Session = Depends(get_session)):
    return [_out(r) for r in get_routines(session)]


@router.post("/routines", status_code=201)
def add_routine(body: RoutineCreate, session: Session = Depends(get_session)):
    r = create_routine(session, **body.model_dump())
    return _out(r)


@router.patch("/routines/{routine_id}")
def patch_routine(routine_id: int, body: RoutinePatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    r = update_routine(session, routine_id, patch)
    if not r:
        raise HTTPException(404)
    return _out(r)


@router.delete("/routines/{routine_id}", status_code=204)
def remove_routine(routine_id: int, session: Session = Depends(get_session)):
    if not delete_routine(session, routine_id):
        raise HTTPException(404)


@router.post("/routines/{routine_id}/run")
def run_routine(routine_id: int, session: Session = Depends(get_session)):
    r = get_routine(session, routine_id)
    if not r:
        raise HTTPException(404)
    result = execute_routine(session, routine_id)
    return {"result": result}


# ─── Kill switch global + journal d'audit (#217) ──────────────────────────────

class KillSwitchPatch(BaseModel):
    enabled: bool


@router.get("/routines/kill-switch")
def read_kill_switch():
    """État du kill switch global des automatisations."""
    return {"enabled": bool(get_preferences().get("automatisations_kill_switch"))}


@router.post("/routines/kill-switch")
def set_kill_switch(body: KillSwitchPatch):
    """Active/désactive le kill switch global (bloque toutes les routines)."""
    prefs = set_preferences({"automatisations_kill_switch": body.enabled})
    return {"enabled": bool(prefs.get("automatisations_kill_switch"))}


@router.get("/routines/runs")
def list_routine_runs(
    limit: int = 50,
    routine_id: int | None = None,
    session: Session = Depends(get_session),
):
    """Journal d'audit des déclenchements (plus récent en premier)."""
    runs = get_routine_runs(session, limit=limit, routine_id=routine_id)
    return [r.model_dump() for r in runs]


# ─── File d'automatisations : ré-exécution + rollback (#216) ───────────────────

@router.post("/routines/runs/{run_id}/rerun")
def rerun_routine_run(run_id: int, session: Session = Depends(get_session)):
    """Ré-exécute la routine d'un run passé (crée un nouveau run)."""
    try:
        return {"result": rerun_run(session, run_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/routines/runs/{run_id}/rollback")
def rollback_routine_run(run_id: int, session: Session = Depends(get_session)):
    """Annule les artefacts réversibles d'un run (notifications créées)."""
    try:
        return {"result": rollback_run(session, run_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/routines/builder-options")
def routine_builder_options():
    """Options du constructeur no-code : événements, jobs, types d'action (#205)."""
    from app.services.automatisations.builder import builder_options
    return builder_options()


# ─── Recettes cross-module (#215) ─────────────────────────────────────────────

@router.get("/recipes")
def list_recipes():
    """Recettes (chaînes d'actions cross-module) lançables à la demande."""
    from app.services.automatisations.recipes import get_recipes
    return get_recipes()


@router.post("/recipes/{recipe_id}/run")
def run_recipe_endpoint(recipe_id: str, session: Session = Depends(get_session)):
    """Exécute une recette (avec confirmation unique côté UI)."""
    from app.services.automatisations.recipes import get_recipe, run_recipe
    if get_recipe(recipe_id) is None:
        raise HTTPException(404, detail="Recette introuvable")
    return {"result": run_recipe(session, recipe_id)}


# ─── Templates (#206) ─────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates():
    return get_templates()


@router.post("/templates/{template_id}/activate", status_code=201)
def activate_template(template_id: str, session: Session = Depends(get_session)):
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(404, detail="Template introuvable")
    payload = {k: v for k, v in tpl.items() if k != "id"}
    r = create_routine(session, **payload)
    return _out(r)


# ─── Journal de vie / Snapshot (#212) ─────────────────────────────────────────

@router.get("/snapshot")
def list_snapshots(days: int = 30, session: Session = Depends(get_session)):
    import json
    snaps = get_recent_snapshots(session, days=days)
    return [{"date": s.date, "data": json.loads(s.data)} for s in snaps]


@router.get("/snapshot/{date_str}")
def get_snapshot_by_date(date_str: str, session: Session = Depends(get_session)):
    import json
    try:
        date = dt.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    snap = get_snapshot(session, date)
    if not snap:
        # Calcul à la volée si absent
        data = build_daily_snapshot(session, date)
        return {"date": date, "data": data, "cached": False}
    return {"date": snap.date, "data": json.loads(snap.data), "cached": True}


@router.post("/snapshot/{date_str}/rebuild")
def rebuild_snapshot(date_str: str, session: Session = Depends(get_session)):
    import json
    try:
        date = dt.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    snap = save_snapshot(session, date)
    return {"date": snap.date, "data": json.loads(snap.data)}


# ─── Score bien-être (#222) ───────────────────────────────────────────────────

@router.get("/wellbeing")
def get_wellbeing(date: str | None = None, session: Session = Depends(get_session)):
    try:
        d = dt.date.fromisoformat(date) if date else dt.date.today()
    except ValueError:
        raise HTTPException(400, detail="Date invalide")
    data = build_daily_snapshot(session, d)
    return {"date": d, **compute_wellbeing_score(data)}


# ─── Mode vacances (#207) ─────────────────────────────────────────────────────

@router.get("/vacances")
def get_vacation_mode():
    from app.services.settings import get_preferences
    return {"mode_vacances": get_preferences().get("mode_vacances", False)}


@router.post("/vacances")
def set_vacation_mode(enabled: bool, session: Session = Depends(get_session)):
    from app.services.settings import set_preferences
    prefs = set_preferences({"mode_vacances": enabled})
    return {"mode_vacances": prefs.get("mode_vacances", False)}


# ─── Courses auto (#208) ─────────────────────────────────────────────────────

@router.get("/courses/low-stock")
def get_low_stock():
    from app.services.automatisations.courses import check_pantry_low_stock
    return check_pantry_low_stock()


@router.post("/courses/check")
def trigger_courses_check(session: Session = Depends(get_session)):
    from app.services.automatisations.courses import run_courses_check
    n = run_courses_check(session)
    return {"items_sous_seuil": n}


# ─── Réappro skincare (#209) ─────────────────────────────────────────────────

@router.get("/skincare/reorder")
def get_skincare_reorder(session: Session = Depends(get_session)):
    from app.services.automatisations.reapprovisionnement import check_skincare_reorder
    return check_skincare_reorder(session)


@router.post("/skincare/reorder-check")
def trigger_skincare_reorder(session: Session = Depends(get_session)):
    from app.services.automatisations.reapprovisionnement import run_skincare_reorder_check
    n = run_skincare_reorder_check(session)
    return {"produits_a_renouveler": n}


# ─── Semaine auto (#210) ─────────────────────────────────────────────────────

@router.get("/semaine-auto")
def get_semaine_auto(
    week_start: str | None = None,
    dry_run: bool = True,
    session: Session = Depends(get_session),
):
    try:
        ws = dt.date.fromisoformat(week_start) if week_start else _current_monday()
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    from app.services.automatisations.semaine_auto import fill_week_auto
    suggestions = fill_week_auto(session, week_start=ws, dry_run=dry_run)
    return {"week_start": ws.isoformat(), "events": suggestions, "count": len(suggestions)}


@router.post("/semaine-auto/apply")
def apply_semaine_auto(
    week_start: str | None = None,
    session: Session = Depends(get_session),
):
    try:
        ws = dt.date.fromisoformat(week_start) if week_start else _current_monday()
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    from app.services.automatisations.semaine_auto import fill_week_auto
    created = fill_week_auto(session, week_start=ws, dry_run=False)
    return {"week_start": ws.isoformat(), "created": len(created)}


def _current_monday() -> dt.date:
    today = dt.date.today()
    return today - dt.timedelta(days=today.weekday())


# ─── Planificateur deep work (#220) ───────────────────────────────────────────

@router.get("/deep-work")
def get_deep_work(
    week_start: str | None = None,
    n_blocks: int = 5,
    session: Session = Depends(get_session),
):
    """Aperçu des blocs de concentration proposés (jours les moins chargés d'abord)."""
    try:
        ws = dt.date.fromisoformat(week_start) if week_start else _current_monday()
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    from app.services.automatisations.deep_work import plan_deep_work
    blocks = plan_deep_work(session, ws, n_blocks=n_blocks, dry_run=True)
    return {"week_start": ws.isoformat(), "blocks": blocks, "count": len(blocks)}


@router.post("/deep-work/apply")
def apply_deep_work(
    week_start: str | None = None,
    n_blocks: int = 5,
    session: Session = Depends(get_session),
):
    try:
        ws = dt.date.fromisoformat(week_start) if week_start else _current_monday()
    except ValueError:
        raise HTTPException(400, detail="Date invalide (YYYY-MM-DD)")
    from app.services.automatisations.deep_work import plan_deep_work
    created = plan_deep_work(session, ws, n_blocks=n_blocks, dry_run=False)
    return {"week_start": ws.isoformat(), "created": len(created)}


# ─── Rééquilibrage budget (#211) ─────────────────────────────────────────────

@router.get("/budget/rebalancing")
def get_budget_rebalancing(mois: str | None = None, session: Session = Depends(get_session)):
    from app.services.automatisations.budget_rebalancing import (
        compute_rebalancing,
    )
    from app.services.budget.envelopes import get_envelope_status
    m = mois or dt.date.today().strftime("%Y-%m")
    statuts = get_envelope_status(session, m)
    suggestions = compute_rebalancing(statuts)
    return {"mois": m, "suggestions": suggestions, "count": len(suggestions)}


@router.post("/budget/rebalancing/apply")
def apply_budget_rebalancing(mois: str | None = None, session: Session = Depends(get_session)):
    from app.services.automatisations.budget_rebalancing import run_monthly_rebalancing
    m = mois or dt.date.today().strftime("%Y-%m")
    suggestions = run_monthly_rebalancing(session, mois=m)
    return {"mois": m, "suggestions": suggestions, "count": len(suggestions)}


# ─── Anomalies (#213) ─────────────────────────────────────────────────────────

@router.get("/anomalies")
def get_anomalies(session: Session = Depends(get_session)):
    from app.services.automatisations.anomalies import (
        detect_weight_anomaly,
        detect_sleep_anomaly,
        detect_expense_anomaly,
        _get_weight_series,
        _get_sleep_series,
        _get_weekly_expense_series,
    )
    today = dt.date.today()
    return {
        "poids": detect_weight_anomaly(_get_weight_series(session, today)),
        "sommeil": detect_sleep_anomaly(_get_sleep_series(session, today)),
        "depenses": detect_expense_anomaly(_get_weekly_expense_series(session, today)),
    }


@router.post("/anomalies/check")
def trigger_anomaly_check(session: Session = Depends(get_session)):
    from app.services.automatisations.anomalies import run_anomaly_detection
    anomalies = run_anomaly_detection(session)
    return {"anomalies": anomalies, "count": len(anomalies)}


# ─── Suggestions d'automatisation apprises des habitudes (#218) ────────────────

@router.get("/suggestions")
def get_automation_suggestions(session: Session = Depends(get_session)):
    """Patterns récurrents (même titre, même jour de semaine) proposés à l'automatisation."""
    from app.services.automatisations.suggestions import suggest_automations
    suggestions = suggest_automations(session)
    return {"suggestions": suggestions, "count": len(suggestions)}


# ─── Webhook entrant (#219) ───────────────────────────────────────────────────

@router.post("/webhooks/{token}")
def trigger_incoming_webhook(token: str, session: Session = Depends(get_session)):
    """Déclenche la routine associée à ce token de webhook (le token = secret)."""
    try:
        return {"result": trigger_webhook(session, token)}
    except ValueError:
        raise HTTPException(404, "Webhook inconnu")
