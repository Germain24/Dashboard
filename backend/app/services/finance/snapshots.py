"""Gestion des snapshots quotidiens de portefeuille."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.finance import SnapshotPortefeuille


def get_latest_snapshot(session: Session) -> SnapshotPortefeuille | None:
    return session.exec(
        select(SnapshotPortefeuille).order_by(SnapshotPortefeuille.date.desc()).limit(1)
    ).first()


def get_history(
    session: Session,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = 365,
) -> list[SnapshotPortefeuille]:
    """Retourne les `limit` snapshots les plus RECENTS, en ordre chronologique.

    (Avant : renvoyait les plus anciens -> le graphique restait bloque sur 2020.)
    """
    q = select(SnapshotPortefeuille)
    if date_from:
        q = q.where(SnapshotPortefeuille.date >= date_from)
    if date_to:
        q = q.where(SnapshotPortefeuille.date <= date_to)
    q = q.order_by(SnapshotPortefeuille.date.desc()).limit(limit)
    rows = list(session.exec(q).all())
    rows.reverse()  # remettre en ordre chronologique croissant pour l'affichage
    return rows


def upsert_snapshot(
    session: Session, date: dt.date, valeur: float, investit: float
) -> SnapshotPortefeuille:
    """Crée ou met à jour le snapshot du jour. Idempotent (race condition safe)."""
    from sqlalchemy.exc import IntegrityError
    existing = session.exec(
        select(SnapshotPortefeuille).where(SnapshotPortefeuille.date == date)
    ).first()
    if existing:
        existing.valeur = valeur
        existing.investit = investit
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    snap = SnapshotPortefeuille(date=date, valeur=valeur, investit=investit)
    session.add(snap)
    try:
        session.commit()
        session.refresh(snap)
        return snap
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(SnapshotPortefeuille).where(SnapshotPortefeuille.date == date)
        ).first()
        return existing


def drop_alert_pct(prev_valeur: float, new_valeur: float, seuil_pct: float = 5.0) -> float | None:
    """Retourne le % de baisse si la chute dépasse ``seuil_pct``, sinon None.

    Ex. prev=100, new=92, seuil=5 -> 8.0 (alerte). prev=100, new=97 -> None.
    """
    if prev_valeur is None or prev_valeur <= 0 or new_valeur is None:
        return None
    drop = (prev_valeur - new_valeur) / prev_valeur * 100
    return round(drop, 2) if drop > seuil_pct else None


def take_snapshot_now(session: Session) -> SnapshotPortefeuille | None:
    """Prend un snapshot live depuis yfinance (positions DB + prix courants).

    Requiert des positions dans la table `position`. Si vide, retourne None.
    """
    try:
        import yfinance as yf

        from app.models.finance import Position
        positions = list(session.exec(select(Position)).all())
        if not positions:
            return None

        total_valeur = 0.0
        total_investit = 0.0
        for pos in positions:
            try:
                from app.services.finance.yf_session import yf_session
                info = yf.Ticker(pos.ticker, session=yf_session()).fast_info
                prix = float(info.get("last_price", 0) or 0)
            except Exception:
                prix = 0.0
            total_valeur += prix * pos.quantite
            if pos.pmu:
                total_investit += pos.pmu * pos.quantite

        if total_valeur == 0:
            return None
        snap = upsert_snapshot(session, dt.date.today(), total_valeur, total_investit)
        # L'Excel reste la source editable : on y reporte le snapshot du jour.
        try:
            from app.services.finance.history_excel import write_snapshot_to_excel
            write_snapshot_to_excel(snap.date, snap.valeur, snap.investit)
        except Exception:
            pass
        return snap
    except Exception as e:
        print(f"[snapshots] Erreur take_snapshot_now: {e}")
        return None
