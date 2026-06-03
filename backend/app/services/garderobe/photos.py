"""Photos de vêtements stockées localement (#75).

La photo est écrite dans `data/garderobe_photos/` et son URL relative est
conservée dans `Vetement.extra["photo_url"]` (pas de migration). Le montage
StaticFiles `/media/garderobe` (cf. main.py) la sert au front.

La détection de couleur dominante est faite côté navigateur (canvas) puis
transmise ici : on la stocke dans `extra["couleur_dominante"]` et, si la pièce
n'a pas encore de couleur, on l'utilise comme couleur par défaut.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from app.core.config import settings
from app.models.garderobe import Vetement

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MEDIA_URL_PREFIX = "/media/garderobe"


def photos_dir() -> Path:
    return settings.data_dir / "garderobe_photos"


def _ext_of(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_EXT else ".jpg"


def _safe_id(vid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", vid)


def save_vetement_photo(
    session: Session,
    vetement_id: str,
    filename: str,
    content: bytes,
    *,
    couleur_dominante: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> Vetement:
    """Sauvegarde la photo d'un vêtement et met à jour son `extra`.

    Lève `KeyError` si le vêtement n'existe pas.
    """
    if not content:
        raise ValueError("Image vide")
    v = session.get(Vetement, vetement_id)
    if v is None:
        raise KeyError(vetement_id)

    directory = base_dir or photos_dir()
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{_safe_id(vetement_id)}{_ext_of(filename)}"
    (directory / name).write_bytes(content)

    extra = dict(v.extra or {})
    extra["photo_url"] = f"{MEDIA_URL_PREFIX}/{name}"
    if couleur_dominante:
        extra["couleur_dominante"] = couleur_dominante
        if not v.couleur:
            v.couleur = couleur_dominante
    v.extra = extra
    v.updated_at = dt.datetime.utcnow()
    session.add(v)
    session.commit()
    session.refresh(v)
    return v
