"""Export/import complet des données (#174/#175/#179) + export CSV (#181).

Découvre dynamiquement toutes les tables SQLModel via le registre SQLAlchemy :
un nouveau module est inclus automatiquement, sans maintenance.
"""

from __future__ import annotations

import csv
import datetime as dt
from app.core.timeutil import utcnow
import io
from typing import Any

from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401  — garantit l'enregistrement de toutes les tables

EXPORT_VERSION = 1


def table_models() -> dict[str, type]:
    """{nom_table: classe SQLModel} pour toutes les tables mappées."""
    out: dict[str, type] = {}
    for mapper in SQLModel._sa_registry.mappers:  # type: ignore[attr-defined]
        cls = mapper.class_
        tn = getattr(cls, "__tablename__", None)
        if tn:
            out[tn] = cls
    return dict(sorted(out.items()))


def _json_safe(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    return value


def _row_to_dict(row) -> dict:
    return {k: _json_safe(v) for k, v in row.model_dump().items()}


def export_all(session: Session) -> dict:
    """Dump complet : {version, exported_at, tables: {nom: [lignes]}}."""
    models = table_models()
    tables: dict[str, list[dict]] = {}
    for name, cls in models.items():
        rows = session.exec(select(cls)).all()
        tables[name] = [_row_to_dict(r) for r in rows]
    return {
        "version": EXPORT_VERSION,
        "exported_at": utcnow().isoformat(),
        "tables": tables,
    }


def import_all(session: Session, data: dict, *, mode: str = "replace") -> dict:
    """Restaure un backup JSON. Valide chaque ligne (Pydantic, #179).

    mode="replace" : vide chaque table présente dans le backup avant insertion.
    mode="merge"   : insère sans vider (peut créer des doublons d'ID -> erreurs).
    Retourne un rapport {tables: {nom: {inserted, errors:[...]}}, total_inserted}.
    """
    models = table_models()
    payload = data.get("tables", data if "tables" not in data else {})
    report: dict[str, Any] = {"tables": {}, "total_inserted": 0, "skipped_tables": []}

    for name, rows in payload.items():
        cls = models.get(name)
        if cls is None:
            report["skipped_tables"].append(name)
            continue
        if mode == "replace":
            for existing in session.exec(select(cls)).all():
                session.delete(existing)
            session.commit()

        inserted = 0
        errors: list[dict] = []
        for i, raw in enumerate(rows or []):
            try:
                # model_validate (≠ cls(**raw)) valide ET coerce les chaînes ISO
                # en date/datetime — indispensable car les modèles table=True ne
                # valident pas à l'init. Sert aussi de validation stricte (#179).
                obj = cls.model_validate(raw)
                session.add(obj)
                session.commit()
                inserted += 1
            except Exception as e:          # ligne invalide -> rapport, on continue
                session.rollback()
                errors.append({"index": i, "error": str(e)[:300]})
        report["tables"][name] = {"inserted": inserted, "errors": errors}
        report["total_inserted"] += inserted

    return report


def export_table_csv(session: Session, table: str) -> str | None:
    """Exporte une table en CSV (#181). None si la table est inconnue."""
    cls = table_models().get(table)
    if cls is None:
        return None
    rows = session.exec(select(cls)).all()
    buf = io.StringIO()
    if not rows:
        # En-têtes depuis le schéma du modèle.
        fields = list(cls.model_fields.keys())
        csv.writer(buf).writerow(fields)
        return buf.getvalue()
    dicts = [_row_to_dict(r) for r in rows]
    writer = csv.DictWriter(buf, fieldnames=list(dicts[0].keys()))
    writer.writeheader()
    for d in dicts:
        writer.writerow(d)
    return buf.getvalue()
