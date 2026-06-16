"""Patrimoine net : actifs manuels (RealT…) + passifs (emprunts).

Agrège le portefeuille actions (dernier snapshot, sans appel yfinance) avec des
avoirs/dettes saisis à la main pour donner un patrimoine net.
`compute_net_worth` est pur (testable) ; le reste lit/écrit en base.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.finance import SnapshotPortefeuille
from app.models.patrimoine import PatrimoineItem


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
) -> dict[str, Any]:
    """Vue patrimoine net complète, tout en EUR.

    Le portefeuille (CAD) est converti en EUR pour rester cohérent avec les
    actifs/passifs saisis en EUR. `cad_eur` permet d'injecter le taux (tests).
    """
    rate = cad_eur if cad_eur is not None else _cad_to_eur(session)
    items = list_items(session)
    portef_eur = portfolio_value(session) * rate
    summary = compute_net_worth(portef_eur, items)
    return {**summary, "taux_cad_eur": round(rate, 4), "items": [i.model_dump() for i in items]}
