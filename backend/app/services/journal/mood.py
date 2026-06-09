"""CRUD humeur (1 entrée/jour) + agrégations pures (#476)."""
from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.journal import MoodEntry


def _validate(humeur: int, energie: int) -> None:
    for name, v in (("humeur", humeur), ("energie", energie)):
        if not (1 <= int(v) <= 5):
            raise ValueError(f"{name} doit être entre 1 et 5")


def upsert_entry(session: Session, date: dt.date, humeur: int, energie: int,
                 tags: list[str], note: str = "") -> MoodEntry:
    _validate(humeur, energie)
    entry = session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()
    if entry is None:
        entry = MoodEntry(date=date, humeur=humeur, energie=energie, tags=list(tags), note=note)
    else:
        entry.humeur = humeur
        entry.energie = energie
        entry.tags = list(tags)
        entry.note = note
        entry.updated_at = dt.datetime.utcnow()
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def get_entry(session: Session, date: dt.date) -> MoodEntry | None:
    return session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()


def list_entries(session: Session, debut: dt.date, fin: dt.date) -> list[MoodEntry]:
    return list(session.exec(
        select(MoodEntry).where(MoodEntry.date >= debut).where(MoodEntry.date <= fin)
        .order_by(MoodEntry.date)  # type: ignore[arg-type]
    ).all())


def delete_entry(session: Session, date: dt.date) -> bool:
    entry = get_entry(session, date)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True


def _moving_average(values: list[float], window: int = 7) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def mood_trends(entries: list[dict]) -> dict:
    """Agrégations déterministes : moyennes, moyenne mobile 7j, distribution, tags."""
    rows = sorted(entries, key=lambda e: e["date"])
    n = len(rows)
    if n == 0:
        return {"n": 0, "moyenne_humeur": 0.0, "moyenne_energie": 0.0,
                "humeur_ma7": [], "energie_ma7": [],
                "distribution_humeur": {str(i): 0 for i in range(1, 6)}, "tags_freq": []}

    humeurs = [float(r["humeur"]) for r in rows]
    energies = [float(r["energie"]) for r in rows]
    dates = [str(r["date"]) for r in rows]
    ma_h = _moving_average(humeurs)
    ma_e = _moving_average(energies)

    distribution = {str(i): 0 for i in range(1, 6)}
    for h in humeurs:
        distribution[str(int(h))] += 1

    counts: dict[str, int] = {}
    for r in rows:
        for tag in r.get("tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    tags_freq = [{"tag": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    return {
        "n": n,
        "moyenne_humeur": round(sum(humeurs) / n, 2),
        "moyenne_energie": round(sum(energies) / n, 2),
        "humeur_ma7": [{"date": d, "value": v} for d, v in zip(dates, ma_h)],
        "energie_ma7": [{"date": d, "value": v} for d, v in zip(dates, ma_e)],
        "distribution_humeur": distribution,
        "tags_freq": tags_freq,
    }
