"""Journal de vie quotidien (#212) — snapshot unifié multi-modules.

Construit un agrégat JSON du jour : habitudes, budget, santé, humeur,
entraînement. Consulté par /automatisations/snapshot?date=.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlmodel import Session, select

from app.models.snapshot import DailySnapshot


# ─── Construction ──────────────────────────────────────────────────────────────

def build_daily_snapshot(session: Session, date: dt.date | None = None) -> dict:
    """Agrège les données de tous les modules pour une date donnée."""
    date = date or dt.date.today()
    data: dict = {"date": date.isoformat()}

    # Habitudes
    try:
        from app.services.habitudes.entries import get_today_checklist
        checklist = get_today_checklist(session, today=date)
        total = len(checklist)
        done = sum(1 for item in checklist if item.get("entry") is not None)
        data["habitudes"] = {"done": done, "total": total, "pct": int(done * 100 / total) if total else 0}
    except Exception:
        pass

    # Budget
    try:
        from app.services.budget.transactions import get_transactions
        txs = get_transactions(session, from_date=date, to_date=date)
        depenses = [t for t in txs if t.montant < 0]
        revenus = [t for t in txs if t.montant > 0]
        data["budget"] = {
            "nb_transactions": len(txs),
            "depenses_total": round(abs(sum(t.montant for t in depenses)), 2),
            "revenus_total": round(sum(t.montant for t in revenus), 2),
        }
    except Exception:
        pass

    # Santé (poids + conso)
    try:
        from app.models.sante import MesureSante
        mesure = session.exec(
            select(MesureSante).where(MesureSante.date == date)
        ).first()
        if mesure:
            sante_data: dict = {}
            if mesure.poids:
                sante_data["poids"] = float(mesure.poids)
            if mesure.extra:
                extra = json.loads(mesure.extra) if isinstance(mesure.extra, str) else mesure.extra
                if "calories" in extra:
                    sante_data["calories"] = extra["calories"]
            data["sante"] = sante_data
    except Exception:
        pass

    # Humeur
    try:
        from app.models.journal import MoodEntry
        mood = session.exec(
            select(MoodEntry).where(MoodEntry.date == date)
        ).first()
        if mood:
            data["humeur"] = {"valeur": mood.humeur, "energie": mood.energie}
    except Exception:
        pass

    # Entraînement
    try:
        from app.models.entrainement import Seance
        seances = session.exec(
            select(Seance).where(Seance.date == date)
        ).all()
        if seances:
            data["entrainement"] = {
                "nb_seances": len(seances),
                "tonnage_kg": sum(getattr(s, "tonnage_kg", 0) or 0 for s in seances),
            }
    except Exception:
        pass

    # Agenda
    try:
        from app.services.agenda.events import get_full_calendar
        from_dt = dt.datetime.combine(date, dt.time.min)
        to_dt = dt.datetime.combine(date, dt.time.max)
        events = get_full_calendar(session, from_dt, to_dt)
        data["agenda"] = {"nb_evenements": len(events)}
    except Exception:
        pass

    return data


# ─── Persistance ──────────────────────────────────────────────────────────────

def save_snapshot(session: Session, date: dt.date | None = None) -> DailySnapshot:
    date = date or dt.date.today()
    data = build_daily_snapshot(session, date)
    existing = session.exec(
        select(DailySnapshot).where(DailySnapshot.date == date)
    ).first()
    if existing:
        existing.data = json.dumps(data, ensure_ascii=False)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    snap = DailySnapshot(date=date, data=json.dumps(data, ensure_ascii=False))
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def get_snapshot(session: Session, date: dt.date) -> DailySnapshot | None:
    return session.exec(
        select(DailySnapshot).where(DailySnapshot.date == date)
    ).first()


def get_recent_snapshots(session: Session, days: int = 30) -> list[DailySnapshot]:
    cutoff = dt.date.today() - dt.timedelta(days=days)
    return list(session.exec(
        select(DailySnapshot)
        .where(DailySnapshot.date >= cutoff)
        .order_by(DailySnapshot.date.desc())
    ).all())
