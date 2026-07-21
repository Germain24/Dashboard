"""Suivi de compétences (skill tree) : niveaux 1-5 et preuves horodatées (#352).

Chaque compétence a un nom, une catégorie libre, un niveau (1-5) et une liste
de preuves (courtes notes datées attestant une progression, ex. "Terminé le
cours X"). Stockage JSON local (`data/etudes_skills.json`), sans migration.

`skills_by_category` et `overall_stats` sont purs et testables sans I/O.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

NIVEAU_MIN = 1
NIVEAU_MAX = 5


def skills_file() -> Path:
    from app.core.config import settings
    return settings.data_dir / "etudes_skills.json"


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(path: Path, skills: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(skills, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(skills: list[dict[str, Any]]) -> int:
    return max((s.get("id", 0) for s in skills), default=0) + 1


def list_skills(*, path: Optional[Path] = None) -> list[dict[str, Any]]:
    return _read(path or skills_file())


def add_skill(
    nom: str,
    categorie: str,
    niveau: int = 1,
    *,
    path: Optional[Path] = None,
    today: Optional[dt.date] = None,
) -> dict[str, Any]:
    if not (NIVEAU_MIN <= niveau <= NIVEAU_MAX):
        raise ValueError(f"niveau doit être entre {NIVEAU_MIN} et {NIVEAU_MAX}")
    today = today or dt.date.today()
    p = path or skills_file()
    skills = _read(p)
    skill: dict[str, Any] = {
        "id": _next_id(skills),
        "nom": nom.strip(),
        "categorie": categorie.strip() or "Autre",
        "niveau": int(niveau),
        "preuves": [],
        "cree_le": today.isoformat(),
    }
    skills.append(skill)
    _write(p, skills)
    return skill


def update_skill(
    skill_id: int,
    patch: dict[str, Any],
    *,
    path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Met à jour nom/categorie/niveau. Ne touche jamais `preuves` (voir add_preuve)."""
    p = path or skills_file()
    skills = _read(p)
    allowed = {"nom", "categorie", "niveau"}
    safe_patch = {k: v for k, v in patch.items() if k in allowed}
    if "niveau" in safe_patch and not (NIVEAU_MIN <= safe_patch["niveau"] <= NIVEAU_MAX):
        raise ValueError(f"niveau doit être entre {NIVEAU_MIN} et {NIVEAU_MAX}")
    for i, skill in enumerate(skills):
        if skill.get("id") == skill_id:
            skills[i] = {**skill, **safe_patch}
            _write(p, skills)
            return skills[i]
    return None


def remove_skill(skill_id: int, *, path: Optional[Path] = None) -> bool:
    p = path or skills_file()
    skills = _read(p)
    new = [s for s in skills if s.get("id") != skill_id]
    if len(new) == len(skills):
        return False
    _write(p, new)
    return True


def add_preuve(
    skill_id: int,
    texte: str,
    *,
    date: Optional[str] = None,
    path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Ajoute une preuve horodatée (date du jour si non fournie), plus récente en tête."""
    p = path or skills_file()
    skills = _read(p)
    date_str = date or dt.date.today().isoformat()
    for i, skill in enumerate(skills):
        if skill.get("id") == skill_id:
            preuve = {"date": date_str, "texte": texte.strip()}
            preuves = list(skill.get("preuves", []))
            preuves.insert(0, preuve)
            preuves.sort(key=lambda p: p.get("date", ""), reverse=True)
            skills[i] = {**skill, "preuves": preuves}
            _write(p, skills)
            return skills[i]
    return None


def skills_by_category(skills: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pur : regroupe les compétences par catégorie avec niveau moyen."""
    par_categorie: dict[str, list[dict[str, Any]]] = {}
    for s in skills:
        par_categorie.setdefault(s.get("categorie", "Autre"), []).append(s)

    result: dict[str, dict[str, Any]] = {}
    for categorie, items in par_categorie.items():
        niveaux = [s.get("niveau", 0) for s in items]
        niveau_moyen = round(sum(niveaux) / len(niveaux), 1) if niveaux else 0.0
        competences = [s.get("nom", "") for s in sorted(items, key=lambda s: s.get("niveau", 0), reverse=True)]
        result[categorie] = {
            "niveau_moyen": niveau_moyen,
            "nb_competences": len(items),
            "competences": competences,
        }
    return result


def overall_stats(skills: list[dict[str, Any]]) -> dict[str, Any]:
    """Pur : statistiques globales tous ensembles."""
    if not skills:
        return {"nb_competences": 0, "niveau_moyen": 0.0, "nb_preuves_total": 0}
    niveaux = [s.get("niveau", 0) for s in skills]
    nb_preuves_total = sum(len(s.get("preuves", [])) for s in skills)
    return {
        "nb_competences": len(skills),
        "niveau_moyen": round(sum(niveaux) / len(niveaux), 1),
        "nb_preuves_total": nb_preuves_total,
    }
