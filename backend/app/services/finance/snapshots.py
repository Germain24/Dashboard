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


def downsample_history(
    rows: list[SnapshotPortefeuille], max_points: int
) -> list[SnapshotPortefeuille]:
    """Réduit uniformément une longue série en conservant ses deux extrémités."""
    if max_points < 2 or len(rows) <= max_points:
        return rows
    last = len(rows) - 1
    indexes = [round(i * last / (max_points - 1)) for i in range(max_points)]
    return [rows[index] for index in dict.fromkeys(indexes)]


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
    """Prend un snapshot depuis les positions actuelles (ledger si des
    transactions existent, sinon la table Position manuelle -- meme source
    que get_positions(), qui gere deja le cache de prix quotidien)."""
    try:
        from app.services.finance.portfolio import get_positions

        positions = get_positions(session)
        if not positions:
            return None

        # Un prix nul sur une position ouverte produit un faux effondrement du
        # portefeuille. Conserver le snapshot précédent est plus fiable qu'une
        # valorisation partielle destinée aux métriques et aux graphiques.
        if any(
            float(position.get("quantite", 0) or 0) > 0
            and float(position.get("prix_actuel", 0) or 0) <= 0
            for position in positions
        ):
            return None

        total_valeur = sum(p["valeur_actuelle"] for p in positions)
        total_investit = sum((p["pmu"] or 0) * p["quantite"] for p in positions)

        if total_valeur == 0:
            return None
        return upsert_snapshot(session, dt.date.today(), total_valeur, total_investit)
    except Exception as e:
        print(f"[snapshots] Erreur take_snapshot_now: {e}")
        return None
