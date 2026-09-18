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

from sqlalchemy import func
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401  — garantit l'enregistrement de toutes les tables

EXPORT_VERSION = 1


class BackupValidationError(ValueError):
    """The backup cannot be safely restored as a complete operation."""


class BackupRestoreError(RuntimeError):
    """The database rejected a restore; the transaction has been rolled back."""


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


def _validated_payload(
    data: dict,
) -> tuple[dict[str, list[Any]], list[str], list[dict], dict[str, int]]:
    """Parse every known row before touching the database."""
    if not isinstance(data, dict):
        raise BackupValidationError("Le contenu du backup doit être un objet JSON.")

    version = data.get("version")
    if version is not None and (
        not isinstance(version, int) or version < 1 or version > EXPORT_VERSION
    ):
        raise BackupValidationError(f"Version de backup non prise en charge : {version}.")

    if "tables" in data:
        payload = data["tables"]
    else:
        # Compatibilité avec les anciens dumps qui contenaient directement les tables.
        payload = {k: v for k, v in data.items() if k not in {"version", "exported_at"}}
    if not isinstance(payload, dict):
        raise BackupValidationError("La propriété 'tables' doit contenir un objet JSON.")

    models = table_models()
    parsed: dict[str, list[Any]] = {}
    skipped: list[str] = []
    errors: list[dict] = []
    incoming_counts: dict[str, int] = {}
    for name, rows in payload.items():
        if not isinstance(name, str):
            errors.append({"table": str(name), "index": -1, "error": "Nom de table invalide."})
            continue
        cls = models.get(name)
        if cls is None:
            skipped.append(name)
            continue
        if not isinstance(rows, list):
            errors.append({"table": name, "index": -1, "error": "Les lignes doivent être une liste."})
            continue

        parsed[name] = []
        incoming_counts[name] = len(rows)
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict):
                errors.append({"table": name, "index": index, "error": "La ligne doit être un objet JSON."})
                continue
            try:
                # model_validate valide les champs et convertit les dates ISO.
                parsed[name].append(cls.model_validate(raw))
            except Exception as exc:
                errors.append({"table": name, "index": index, "error": str(exc)[:300]})

    return parsed, sorted(skipped), errors, incoming_counts


def preview_import(session: Session, data: dict, *, mode: str = "replace") -> dict:
    """Validate a backup and report its impact without changing database rows."""
    if mode not in ("replace", "merge"):
        raise BackupValidationError("Mode invalide (replace | merge).")
    parsed, skipped, errors, incoming_counts = _validated_payload(data)
    models = table_models()
    table_report: dict[str, dict[str, int]] = {}
    for name, rows in parsed.items():
        current = session.execute(
            select(func.count()).select_from(models[name])
        ).scalar_one()
        table_report[name] = {"incoming": incoming_counts[name], "current": int(current)}

    return {
        "version": data.get("version"),
        "exported_at": data.get("exported_at"),
        "mode": mode,
        "can_import": not errors,
        "total_incoming": sum(incoming_counts.values()),
        "table_count": len(parsed),
        "tables": table_report,
        "skipped_tables": skipped,
        "errors": errors,
    }


def import_all(session: Session, data: dict, *, mode: str = "replace") -> dict:
    """Restore a backup atomically after validating all rows in advance.

    A database constraint error aborts the whole operation. In particular, a
    replace never leaves previously existing data deleted after a partial import.
    """
    if mode not in ("replace", "merge"):
        raise BackupValidationError("Mode invalide (replace | merge).")
    parsed, skipped, errors, _incoming_counts = _validated_payload(data)
    if errors:
        raise BackupValidationError(
            f"Prévalidation refusée : {len(errors)} ligne(s) ou table(s) invalide(s)."
        )

    models = table_models()
    ordered_names = [table.name for table in SQLModel.metadata.sorted_tables if table.name in parsed]
    # Preserve any mapped models not represented in metadata's sorted list.
    ordered_names.extend(name for name in parsed if name not in ordered_names)
    report: dict[str, Any] = {"tables": {}, "total_inserted": 0, "skipped_tables": skipped}

    try:
        if session.in_transaction():
            raise BackupRestoreError("La restauration exige une session sans transaction active.")
        with session.begin():
            if mode == "replace":
                # Delete dependent tables first. The metadata order also keeps this
                # safe if foreign keys are added to models in the future.
                for name in reversed(ordered_names):
                    for existing in session.exec(select(models[name])).all():
                        session.delete(existing)
                    session.flush()

            # Insert parent tables first, flushing each table before dependants.
            for name in ordered_names:
                for obj in parsed[name]:
                    session.add(obj)
                session.flush()
                inserted = len(parsed[name])
                report["tables"][name] = {"inserted": inserted, "errors": []}
                report["total_inserted"] += inserted
    except BackupRestoreError:
        raise
    except Exception as exc:
        raise BackupRestoreError(
            f"Restauration annulée intégralement : {str(exc)[:300]}"
        ) from exc

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
