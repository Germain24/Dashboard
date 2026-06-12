"""Briefings quotidiens (#203 + #204) — fonctions pures de construction."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select


# ─── BRIEFING MATIN (#203) ────────────────────────────────────────────────────

def build_morning_briefing(session: Session, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    lines: list[str] = []
    days_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    months_fr = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    date_str = f"{days_fr[today.weekday()]} {today.day} {months_fr[today.month]}"
    lines.append(f"Bonjour — {date_str}")

    # Agenda du jour
    try:
        from app.services.agenda.events import get_full_calendar
        from_dt = dt.datetime.combine(today, dt.time.min)
        to_dt = dt.datetime.combine(today, dt.time.max)
        events = get_full_calendar(session, from_dt, to_dt)
        events_sorted = sorted(
            [e for e in events if e.get("debut")],
            key=lambda e: e["debut"],
        )
        if events_sorted:
            first = events_sorted[0]
            heure = first["debut"].strftime("%H:%M") if first.get("debut") else "?"
            extra = f" (+{len(events_sorted) - 1})" if len(events_sorted) > 1 else ""
            lines.append(f"📅 {first.get('titre', 'Événement')} à {heure}{extra}")
        else:
            lines.append("📅 Aucun événement aujourd'hui")
    except Exception:
        pass

    # Habitudes à faire
    try:
        from app.services.habitudes.entries import get_today_checklist
        checklist = get_today_checklist(session, today=today)
        total = len(checklist)
        done = sum(1 for item in checklist if item.get("entry") is not None)
        if total:
            lines.append(f"✓ Habitudes : {done}/{total} faites")
    except Exception:
        pass

    # Objectif calorique du jour
    try:
        from app.models.sante import MesureSante
        latest = session.exec(
            select(MesureSante)
            .where(MesureSante.poids.isnot(None))  # type: ignore[attr-defined]
            .order_by(MesureSante.date.desc())  # type: ignore[attr-defined]
        ).first()
        if latest and latest.poids:
            from app.services.sante.targets import calculate_daily_targets
            targets = calculate_daily_targets(float(latest.poids), today)
            kcal = int(targets.get("calories", 0))
            prot = int(targets.get("proteines_g", 0))
            if kcal:
                lines.append(f"🍽️ Objectif : {kcal} kcal / {prot}g protéines")
    except Exception:
        pass

    # Météo / tenue
    try:
        from app.services.garderobe.weather import get_weather
        w = get_weather()
        if w and w.temp_c is not None:
            lines.append(f"🌡️ Météo : {round(w.temp_c)}°C — {w.description or ''}")
    except Exception:
        pass

    return "\n".join(lines)


# ─── RÉCAP SOIR (#204) ────────────────────────────────────────────────────────

def build_evening_recap(session: Session, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    lines: list[str] = []
    months_fr = ["", "jan", "fév", "mars", "avr", "mai", "juin",
                 "juil", "août", "sep", "oct", "nov", "déc"]
    lines.append(f"Récap du {today.day} {months_fr[today.month]}")

    # Dépenses du jour
    try:
        from app.services.budget.transactions import get_transactions
        txs = get_transactions(session, from_date=today, to_date=today)
        depenses = [t for t in txs if t.montant < 0]
        if depenses:
            total = abs(sum(t.montant for t in depenses))
            lines.append(f"💰 Dépenses : {len(depenses)} transaction(s) — {total:.2f} €")
        else:
            lines.append("💰 Aucune dépense aujourd'hui")
    except Exception:
        pass

    # Habitudes
    try:
        from app.services.habitudes.entries import get_today_checklist
        checklist = get_today_checklist(session, today=today)
        total = len(checklist)
        done = sum(1 for item in checklist if item.get("entry") is not None)
        pct = int(done * 100 / total) if total else 0
        if total:
            lines.append(f"✓ Habitudes : {done}/{total} ({pct}%)")
    except Exception:
        pass

    # Agenda de demain
    try:
        from app.services.agenda.events import get_full_calendar
        demain = today + dt.timedelta(days=1)
        from_dt = dt.datetime.combine(demain, dt.time.min)
        to_dt = dt.datetime.combine(demain, dt.time.max)
        events = get_full_calendar(session, from_dt, to_dt)
        if events:
            first = min(events, key=lambda e: e.get("debut") or dt.datetime.max)
            heure = first["debut"].strftime("%H:%M") if first.get("debut") else ""
            extra = f" (+{len(events) - 1})" if len(events) > 1 else ""
            lines.append(f"📅 Demain : {first.get('titre', 'Événement')}{(' à ' + heure) if heure else ''}{extra}")
        else:
            lines.append("📅 Demain : rien de planifié")
    except Exception:
        pass

    return "\n".join(lines)
