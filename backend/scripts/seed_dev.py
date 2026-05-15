"""Données de dev — sera enrichi dans les CONV suivantes.

En CONV 1, ce script se contente d'afficher le contenu DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.models import (  # noqa: E402
    Aliment,
    MesureSante,
    SnapshotPortefeuille,
    Vetement,
    WatchlistEntry,
)


def main() -> None:
    with Session(engine) as s:
        counts = {
            "vetement": len(s.exec(select(Vetement)).all()),
            "aliment": len(s.exec(select(Aliment)).all()),
            "mesure_sante": len(s.exec(select(MesureSante)).all()),
            "snapshot_portefeuille": len(s.exec(select(SnapshotPortefeuille)).all()),
            "watchlist_entry": len(s.exec(select(WatchlistEntry)).all()),
        }
    print("État DB :")
    for k, v in counts.items():
        print(f"  {k:25} {v:>6}")


if __name__ == "__main__":
    main()
