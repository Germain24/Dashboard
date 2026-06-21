"""Patrimoine net : actifs manuels (RealT…) + passifs (emprunts).

Agrège le portefeuille actions (dernier snapshot, sans appel yfinance) avec des
avoirs/dettes saisis à la main pour donner un patrimoine net.
`compute_net_worth` est pur (testable) ; le reste lit/écrit en base.
"""

from __future__ import annotations

import datetime as dt
import re
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


def _norm_key(s: str | None) -> str:
    """Normalise pour le rapprochement libellé↔compte : minuscules, alphanum.

    Ainsi « Trading 212 » (libellé) == clé « trading212 », et « desjardins-eop »
    == « Desjardins »."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _load_auto_balances() -> dict[str, dict]:
    """Soldes connus, indexés par clé normalisée (préfixe du nom de compte).

    "desjardins-eop"/"desjardins-debit" -> clé "desjardins" ; "trading212" ->
    "trading212". Best-effort : un fichier absent/illisible n'empêche jamais le
    calcul du patrimoine.
    """
    try:
        from app.services.finance.account_balances import get_balances
        out: dict[str, dict] = {}
        for compte, info in get_balances().items():
            key = _norm_key(str(compte).split("-")[0])
            if key:
                out[key] = info
        return out
    except Exception:
        return {}


def _match_auto_balance(label: str | None, balances: dict[str, dict]) -> dict | None:
    """Trouve le solde auto correspondant à un libellé (ex. "Trading 212" -> trading212)."""
    if not balances or not label:
        return None
    norm = _norm_key(label)
    for key, info in balances.items():
        if key and key in norm:
            return info
    return None


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
    auto_balances = _load_auto_balances()
    # Chaque ligne est convertie de sa devise vers l'EUR (saisie en monnaie locale).
    converted = []
    dumped = []
    for i in items:
        auto = _match_auto_balance(i.label, auto_balances)
        if auto is not None:
            # Solde importé (relevé) : prime sur la saisie manuelle.
            valeur = round(float(auto["solde"]), 2)
            devise = auto.get("devise") or i.devise
        else:
            valeur, devise = i.valeur, i.devise
        v_eur = to_eur(valeur, devise)
        converted.append(SimpleNamespace(type=i.type, valeur=v_eur))
        d = i.model_dump()
        d["valeur_eur"] = v_eur
        if auto is not None:
            d["valeur"] = valeur
            d["valeur_source"] = "auto"
            d["valeur_auto_date"] = auto.get("date")
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


def _match_history(label: str | None, hist: dict) -> bool:
    """Vrai si un compte du chart d'historique (relevés) correspond au libellé."""
    n = _norm_key(label)
    return any(_norm_key(k) in n or n in _norm_key(k) for k in hist if _norm_key(k))


def net_worth_breakdown_history(session: Session, *, days: int = 365) -> dict[str, Any]:
    """Évolution de la valeur brute (actifs) ventilée PAR COMPTE, en EUR.

    Histogramme empilé mensuel reconstruit depuis les RELEVÉS (valeur de clôture
    de chaque mois, reportée entre relevés, 0 avant le 1er) — remonte aussi loin
    que les relevés le permettent (Banque Populaire dès 2022, Trading212,
    Desjardins). Les comptes sans relevé exploitable (RealT, Wise, Bourse Direct…)
    utilisent leur valeur courante depuis leur date de création. `days` ignoré
    (on part de la donnée la plus ancienne). Voir [[adonis...]]→account_history.
    """
    items = [i for i in list_items(session) if i.type == "actif"]
    if not items:
        return {"dates": [], "comptes": [], "series": {}, "total": []}
    from app.services.finance.account_history import account_history_points, build_daily_series
    try:
        hist = account_history_points()
    except Exception:
        hist = {}
    manual = [
        (i.label, to_eur(i.valeur, i.devise), i.created_at.date())
        for i in items
        if not _match_history(i.label, hist)
    ]
    return build_daily_series(hist, manual)


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
