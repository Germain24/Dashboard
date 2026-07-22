"""Gestion des snapshots quotidiens de portefeuille."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from sqlmodel import Session, select

from app.models.finance import SnapshotPortefeuille, Transaction

_CASH_FLOW_TYPES = ("depot", "retrait")
# Les seules baisses historiques antérieures sont deux trous transitoires de
# 18,46 % et 12,51 %. La rupture de source du 09/06/2026 atteint 28,75 %.
_UNEXPLAINED_DROP_PCT = 20.0


def _cash_flow_amount(transaction: Transaction) -> float:
    """Montant EUR signé d'un apport/retrait du grand livre.

    Les imports broker stockent les mouvements de cash sous la convention
    ``quantite=1`` et ``prix_unitaire=montant``. Le repli sur le prix seul
    conserve la compatibilité avec d'anciennes lignes saisies avec une quantité
    nulle.
    """
    quantity = float(transaction.quantite or 0)
    unit_price = float(transaction.prix_unitaire or 0)
    amount = abs(quantity * unit_price if quantity else unit_price)
    return -amount if str(transaction.type).lower() == "retrait" else amount


def _cash_flow_date(transaction: Transaction) -> dt.date:
    value = transaction.date
    return value.date() if isinstance(value, dt.datetime) else value


def _cash_flow_transactions(session: Session) -> list[Transaction]:
    return list(
        session.exec(
            select(Transaction)
            .where(Transaction.type.in_(_CASH_FLOW_TYPES))
            .order_by(Transaction.date.asc(), Transaction.id.asc())
        ).all()
    )


def _net_cash_flows(
    cash_flows: Iterable[Transaction],
    after: dt.date,
    through: dt.date,
) -> float:
    """Somme signée des flux dans ``]after, through]``."""
    return sum(
        _cash_flow_amount(flow)
        for flow in cash_flows
        if after < _cash_flow_date(flow) <= through
    )


def reconcile_invested_history(
    rows: Iterable[SnapshotPortefeuille],
    cash_flows: Iterable[Transaction],
) -> list[SnapshotPortefeuille]:
    """Préserve l'historique fiable puis réconcilie sa rupture de source.

    Avant une rupture, le montant suit le maximum des valeurs brutes fiables.
    Une petite baisse brute est donc considérée comme une donnée manquante et
    reste constante ; seul un retrait documenté autorise ce maximum à baisser.

    La première baisse inexpliquée d'au moins 20 % fige la dernière ancre fiable.
    À partir de cette date, les valeurs brutes ne sont plus comparables : seuls
    les flux externes documentés postérieurs font varier le capital. Dans la base
    réelle, cela conserve 178,31 -> 21 051,60 € jusqu'au 15/05/2026, neutralise
    la fausse chute à 15 000 €, puis ajoute les dépôts ultérieurs.

    La fonction renvoie des copies afin qu'une simple lecture d'historique ne
    modifie pas silencieusement la base.
    """
    ordered = sorted(rows, key=lambda row: row.date)
    if not ordered:
        return []

    flows = sorted(cash_flows, key=lambda item: (item.date, item.id or 0))
    reconciled = [
        ordered[0].model_copy(
            update={"investit": round(float(ordered[0].investit or 0), 2)}
        )
    ]
    invested = float(ordered[0].investit or 0)
    previous_date = ordered[0].date
    anchor_value: float | None = None
    anchor_date: dt.date | None = None

    for row in ordered[1:]:
        raw = max(0.0, float(row.investit or 0))
        if anchor_value is not None and anchor_date is not None:
            invested = max(
                0.0,
                anchor_value + _net_cash_flows(flows, anchor_date, row.date),
            )
        else:
            interval_flow = _net_cash_flows(flows, previous_date, row.date)
            # Avant la rupture, on combine les deux preuves sans double compter :
            # le brut conserve les anciens apports non documentés, tandis qu'un
            # flux explicite garantit au minimum la variation correspondante.
            expected = max(
                0.0,
                invested + interval_flow,
            )
            drop_pct = (
                (expected - raw) / expected * 100.0
                if expected > 0 and raw < expected
                else 0.0
            )
            if drop_pct >= _UNEXPLAINED_DROP_PCT:
                anchor_value = invested
                anchor_date = previous_date
                invested = max(
                    0.0,
                    anchor_value + _net_cash_flows(flows, anchor_date, row.date),
                )
            else:
                # Un retrait documenté est autoritaire même si le snapshot brut
                # est resté figé. Pour un dépôt, ``max`` évite de compter deux
                # fois une hausse déjà présente dans l'historique brut.
                invested = expected if interval_flow < 0 else max(expected, raw)

        reconciled.append(
            row.model_copy(update={"investit": round(invested, 2)})
        )
        previous_date = row.date
    return reconciled


def carry_forward_partial_values(
    rows: Iterable[SnapshotPortefeuille],
) -> list[SnapshotPortefeuille]:
    """Porte la dernière valorisation complète sur les snapshots partiels.

    La détection commune aux métriques reconnaît une chute brève suivie du
    retour du compte manquant (cas réel Bourse Direct : 27 k€ → 861 € → 28 k€).
    Le graphique conserve toutes ses dates, mais les points retirés de la série
    fiable reçoivent la dernière valeur complète. La base brute reste intacte.
    """
    ordered = sorted(rows, key=lambda row: row.date)
    if not ordered:
        return []

    from app.services.finance.metrics import prepare_metric_snapshots

    reliable_dates = {
        snapshot.date for snapshot in prepare_metric_snapshots(ordered)
    }
    carried: list[SnapshotPortefeuille] = []
    last_reliable_value: float | None = None
    for row in ordered:
        if row.date in reliable_dates:
            last_reliable_value = float(row.valeur)
            carried.append(row)
        elif last_reliable_value is not None:
            carried.append(
                row.model_copy(update={"valeur": round(last_reliable_value, 2)})
            )
        else:
            carried.append(row)
    return carried


def get_latest_snapshot(session: Session) -> SnapshotPortefeuille | None:
    rows = get_history(session, limit=1)
    return rows[-1] if rows else None


def get_history(
    session: Session,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = 365,
) -> list[SnapshotPortefeuille]:
    """Retourne les `limit` snapshots les plus RECENTS, en ordre chronologique.

    (Avant : renvoyait les plus anciens -> le graphique restait bloque sur 2020.)
    """
    # La réconciliation a besoin du point d'ancrage antérieur au début de la
    # fenêtre demandée. On charge donc la série complète, puis on filtre/limite
    # après avoir appliqué les flux documentés.
    rows = list(
        session.exec(
            select(SnapshotPortefeuille).order_by(SnapshotPortefeuille.date.asc())
        ).all()
    )
    flows = _cash_flow_transactions(session)
    rows = reconcile_invested_history(
        rows,
        flows,
    )
    rows = carry_forward_partial_values(rows)
    if date_from:
        rows = [row for row in rows if row.date >= date_from]
    if date_to:
        rows = [row for row in rows if row.date <= date_to]
    return rows[-limit:]


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
    """Prend un snapshot depuis l'état portefeuille, cash compris."""
    try:
        from app.services.finance.portfolio_state import get_portfolio_state

        state = get_portfolio_state(session)
        positions = list(state.get("positions") or [])

        # Un prix nul sur une position ouverte produit un faux effondrement du
        # portefeuille. Conserver le snapshot précédent est plus fiable qu'une
        # valorisation partielle destinée aux métriques et aux graphiques.
        if any(
            float(position.get("quantite", 0) or 0) > 0
            and float(position.get("prix", 0) or 0) <= 0
            for position in positions
        ):
            return None

        # ``valeur_totale`` est la source canonique : contrairement à la somme
        # des seules positions, elle inclut le cash non encore investi.
        total_valeur = float(state.get("valeur_totale") or 0)

        today = dt.date.today()
        flows = _cash_flow_transactions(session)
        previous = get_history(session, date_to=today, limit=1)
        if previous:
            latest = previous[-1]
            total_investit = max(
                0.0,
                float(latest.investit)
                + _net_cash_flows(flows, latest.date, today),
            )
        else:
            # Toute première valorisation seulement : sans historique ni flux
            # antérieur comparable, les apports documentés initialisent l'ancre.
            # En mode positions manuelles (aucun flux), on conserve le coût.
            if flows:
                total_investit = max(0.0, float(state.get("investi_net") or 0))
            else:
                total_investit = sum(
                    (position.get("acb") or 0) * (position.get("quantite") or 0)
                    for position in positions
                )

        if total_valeur == 0:
            return None
        return upsert_snapshot(session, today, total_valeur, round(total_investit, 2))
    except Exception as e:
        print(f"[snapshots] Erreur take_snapshot_now: {e}")
        return None
