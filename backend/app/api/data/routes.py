"""Données — export/import complet + export CSV par table + seed démo (#174-#181)."""

from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app.api.data.schemas import ImportRequest
from app.core.db import get_session
from app.services.data_io import demo as demo_svc
from app.services.data_io import export_import as io_svc
from app.services.backup_storage import backup_bytes

router = APIRouter(prefix="", tags=["data"])


@router.get("/tables")
def tables() -> list[str]:
    """Noms des tables exportables (pour l'UI d'export CSV)."""
    return list(io_svc.table_models().keys())


@router.get("/export")
def export_all(session: Session = Depends(get_session)):
    """Backup JSON complet, téléchargeable (#174)."""
    data = io_svc.export_all(session)
    body = json.dumps(data, ensure_ascii=False, indent=2)
    fname = f"mission-control-backup-{dt.date.today()}.json"
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    try:
        backup_bytes(
            body,
            category="runtime/exports-json",
            filename=f"mission-control-backup-{stamp}.json",
        )
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            503,
            "Sauvegarde NAS indisponible : l'export JSON n'a pas pu être archivé.",
        ) from exc
    return Response(
        content=body, media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/import")
def import_all(body: ImportRequest, session: Session = Depends(get_session)):
    """Restaure un backup en une transaction complète ou ne change rien."""
    try:
        return io_svc.import_all(session, body.data, mode=body.mode)
    except io_svc.BackupValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except io_svc.BackupRestoreError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/import/preview")
def preview_import(body: ImportRequest, session: Session = Depends(get_session)):
    """Prévalide le JSON et montre les tables/lignes concernées sans écriture."""
    try:
        return io_svc.preview_import(session, body.data, mode=body.mode)
    except io_svc.BackupValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/export/{table}.csv")
def export_table_csv(table: str, session: Session = Depends(get_session)):
    """Export CSV d'une table (#181)."""
    csv_str = io_svc.export_table_csv(session, table)
    if csv_str is None:
        raise HTTPException(404, f"Table inconnue : {table}")
    return Response(
        content=csv_str, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}.csv"'},
    )


@router.post("/seed-demo")
def seed_demo(force: bool = False, session: Session = Depends(get_session)):
    """Insère des données de démo réalistes (#178). Refuse si données présentes sauf force."""
    if not force and demo_svc.has_any_data(session):
        raise HTTPException(
            409, "Des données existent déjà. Utilise ?force=true pour ajouter quand même."
        )
    return {"seeded": demo_svc.seed_demo(session)}
