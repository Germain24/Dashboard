"""Réorganise les images pixel art : assets/<catégorie>/<slug>.png + Vetement.image.

One-time. Idempotent : ne refait rien si l'image est déjà à la bonne place.

Usage (depuis backend/) :
    uv run python -m scripts.reorg_garderobe_assets
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models.garderobe import Vetement


def slugify(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


def build_slug(sous_categorie: str | None, marque: str | None, couleur: str | None) -> str:
    parts = [p for p in (slugify(sous_categorie), slugify(marque), slugify(couleur)) if p]
    return "-".join(parts) or "sans-nom"


def assign_paths(rows: list[dict]) -> dict[str, str]:
    """id -> '<categorie>/<slug>.png', dédup déterministe (tri par id croissant)."""
    out: dict[str, str] = {}
    used: dict[str, int] = {}
    for r in sorted(rows, key=lambda r: r["id"]):
        cat = r.get("categorie") or "Autre"
        slug = build_slug(r.get("sous_categorie"), r.get("marque"), r.get("couleur"))
        base = f"{cat}/{slug}"
        n = used.get(base, 0) + 1
        used[base] = n
        out[r["id"]] = f"{base}.png" if n == 1 else f"{base}-{n}.png"
    return out


def _find_source_png(assets_dir: Path, vetement_id: str) -> Path | None:
    """PNG source à plat dont le stem == id (insensible à la casse)."""
    target = vetement_id.casefold()
    for p in assets_dir.glob("*.png"):
        if p.stem.casefold() == target:
            return p
    return None


def _git_mv(repo_root: Path, src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "mv", str(src), str(dst)],
            check=True, capture_output=True,
        )
    except Exception:
        shutil.move(str(src), str(dst))
        subprocess.run(["git", "-C", str(repo_root), "add", str(dst)], check=False)


def main() -> dict:
    assets_dir = settings.repo_root / "frontend" / "public" / "garderobe" / "assets"
    moved = 0
    missing: list[str] = []
    with Session(engine) as s:
        vets = s.exec(select(Vetement)).all()
        rows = [
            {"id": v.id, "categorie": v.categorie, "sous_categorie": v.sous_categorie,
             "marque": v.marque, "couleur": v.couleur}
            for v in vets
        ]
        paths = assign_paths(rows)
        for v in vets:
            rel = paths[v.id]
            dst = assets_dir / rel
            if v.image == rel and dst.exists():
                continue
            src = _find_source_png(assets_dir, v.id)
            if src is None:
                missing.append(v.id)
                continue
            _git_mv(settings.repo_root, src, dst)
            v.image = rel
            moved += 1
        s.commit()
    print(f"déplacés={moved} sans_png={missing}")
    return {"moved": moved, "missing": missing}


if __name__ == "__main__":
    main()
