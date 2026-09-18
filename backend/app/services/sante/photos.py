"""Photos de progression avant/après stockées localement (#69).

Les images sont écrites dans `data/sante_photos/` (hors base SQL) et l'URL
relative est conservée dans `MesureSante.photo_url`. Le montage StaticFiles
`/media/sante` (cf. main.py) les sert au front.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models.sante import MesureSante

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MEDIA_URL_PREFIX = "/media/sante"


def photos_dir() -> Path:
    return settings.data_dir / "sante_photos"


def _ext_of(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_EXT else ".jpg"


def save_progress_photo(
    session: Session,
    date: dt.date,
    filename: str,
    content: bytes,
    *,
    base_dir: Optional[Path] = None,
) -> MesureSante:
    """Sauvegarde l'image et renseigne `photo_url` de la mesure du jour.

    `base_dir` permet d'injecter un répertoire de test ; par défaut
    `data/sante_photos/`.
    """
    if not content:
        raise ValueError("Image vide")
    directory = base_dir or photos_dir()
    directory.mkdir(parents=True, exist_ok=True)
    safe_date = re.sub(r"[^0-9-]", "", str(date))
    name = f"{safe_date}{_ext_of(filename)}"
    (directory / name).write_bytes(content)

    m = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if not m:
        m = MesureSante(date=date)
        session.add(m)
    m.photo_url = f"{MEDIA_URL_PREFIX}/{name}"
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def list_progress_photos(session: Session) -> list[dict]:
    """Mesures disposant d'une photo, triées par date croissante."""
    rows = session.exec(
        select(MesureSante)
        .where(MesureSante.photo_url.isnot(None))
        .order_by(MesureSante.date.asc())
    ).all()
    return [
        {"date": str(m.date), "photo_url": m.photo_url, "poids": m.poids}
        for m in rows
    ]
