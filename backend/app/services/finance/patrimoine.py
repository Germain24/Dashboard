"""Patrimoine net : actifs manuels (RealT…) + passifs (emprunts).

Agrège le portefeuille actions (dernier snapshot, sans appel yfinance) avec des
avoirs/dettes saisis à la main pour donner un patrimoine net.
`compute_net_worth` est pur (testable) ; le reste lit/écrit en base.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from sqlmodel import Session, select

from app.models.finance import SnapshotPortefeuille
from app.models.patrimoine import PatrimoineItem, PatrimoineSnapshot


def to_eur(amount: float, devise: str | None) -> float:
    """Convertit `amount` (dans `devise`) en EUR. Repli sur la valeur brute si
    le taux n'est pas disponible (best-effort)."""
    if not devise or devise.upper() == "EUR":
        return round(float(amount), 2)
    try:
        from app.services.finance.fx import convert
        eur = convert(float(amount), devise.upper(), "EUR")
        return eur if eur else round(float(amount), 2)
    except Exception:
        return round(float(amount), 2)


def compute_net_worth(portfolio_value: float, items: list[Any]) -> dict[str, float]:
    """Patrimoine net = portefeuille + actifs manuels − passifs."""
    actifs = sum(i.valeur for i in items if i.type == "actif")
    passifs = sum(i.valeur for i in items if i.type == "passif")
    return {
        "portefeuille": round(float(portfolio_value), 2),
        "actifs_manuels": round(actifs, 2),
        "passifs": round(passifs, 2),
        "net": round(float(portfolio_value) + actifs - passifs, 2),
    }


def portfolio_value(session: Session) -> float:
    """Valeur brute du portefeuille = dernier snapshot (en CAD, 0 si aucun)."""
    snap = session.exec(
        select(SnapshotPortefeuille).order_by(SnapshotPortefeuille.date.desc())
    ).first()
    return float(snap.valeur) if snap else 0.0


def _cad_to_eur(session: Session) -> float:
    """Taux CAD→EUR best-effort (le portefeuille est libellé en CAD). Repli 0.68."""
    try:
        from app.services.finance.fx import get_rate
        cad_usd = get_rate("CAD", "USD")
        eur_usd = get_rate("EUR", "USD")
        if cad_usd and eur_usd:
            return cad_usd / eur_usd
    except Exception:
        pass
    return 0.68


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def create_item(
    session: Session, *, type: str, label: str, valeur: float,
    categorie: str = "", taux_pct: float | None = None,
    mensualite: float | None = None, devise: str = "EUR",
) -> PatrimoineItem:
    if type not in ("actif", "passif"):
        raise ValueError("type doit être 'actif' ou 'passif'")
    item = PatrimoineItem(
        type=type, label=label, valeur=valeur, categorie=categorie,
        taux_pct=taux_pct, mensualite=mensualite, devise=devise,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_items(session: Session) -> list[PatrimoineItem]:
    return list(session.exec(select(PatrimoineItem).order_by(PatrimoineItem.created_at)).all())


def update_item(session: Session, item_id: int, patch: dict) -> PatrimoineItem | None:
    item = session.get(PatrimoineItem, item_id)
    if not item:
        return None
    from app.core.timeutil import utcnow
    for k, v in patch.items():
        if hasattr(item, k):
            setattr(item, k, v)
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_item(session: Session, item_id: int) -> bool:
    item = session.get(PatrimoineItem, item_id)
    if not item:
        return False
    session.delete(item)
    session.commit()
    return True


def net_worth_summary(
    session: Session, *, cad_eur: float | None = None,
    inclure_portefeuille: bool = False,
) -> dict[str, Any]:
    """Vue patrimoine net complète, tout en EUR.

    Par défaut le patrimoine net = actifs manuels − passifs (l'utilisateur saisit
    lui-même ses comptes-titres). `inclure_portefeuille=True` ajoute en plus le
    portefeuille actions auto (snapshot CAD→EUR) — à n'activer que s'il n'est PAS
    déjà saisi en actif manuel (sinon double comptage). `cad_eur` injecte le taux.
    """
    items = list_items(session)
    # Chaque ligne est convertie de sa devise vers l'EUR (saisie en monnaie locale).
    converted = []
    dumped = []
    for i in items:
        v_eur = to_eur(i.valeur, i.devise)
        converted.append(SimpleNamespace(type=i.type, valeur=v_eur))
        d = i.model_dump()
        d["valeur_eur"] = v_eur
        dumped.append(d)

    if inclure_portefeuille:
        rate = cad_eur if cad_eur is not None else _cad_to_eur(session)
        portef_eur = portfolio_value(session) * rate
    else:
        rate = cad_eur if cad_eur is not None else 0.0
        portef_eur = 0.0

    summary = compute_net_worth(portef_eur, converted)
    return {**summary, "taux_cad_eur": round(rate, 4), "items": dumped}


# ─── Historisation dans le temps (#257) ─────────────────────────────────────

def record_net_worth_snapshot(
    session: Session, *, today: dt.date | None = None,
) -> PatrimoineSnapshot:
    """Enregistre (ou met à jour) la photo du patrimoine net du jour, en EUR.

    Idempotent : une seule ligne par date — un nouvel appel le même jour
    rafraîchit les valeurs au lieu de créer un doublon.
    """
    today = today or dt.date.today()
    summary = net_worth_summary(session)
    snap = session.exec(
        select(PatrimoineSnapshot).where(PatrimoineSnapshot.date == today)
    ).first() or PatrimoineSnapshot(date=today)
    snap.net = summary["net"]
    snap.actifs = summary["actifs_manuels"]
    snap.passifs = summary["passifs"]
    snap.portefeuille = summary["portefeuille"]
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def net_worth_history(session: Session, *, days: int = 365) -> list[dict[str, Any]]:
    """Série chronologique du patrimoine net sur la fenêtre récente (croissant)."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = session.exec(
        select(PatrimoineSnapshot)
        .where(PatrimoineSnapshot.date >= cutoff)
        .order_by(PatrimoineSnapshot.date)
    ).all()
    return [
        {
            "date": r.date.isoformat(), "net": r.net, "actifs": r.actifs,
            "passifs": r.passifs, "portefeuille": r.portefeuille,
        }
        for r in rows
    ]
