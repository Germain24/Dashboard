"""Analytique budget — dépenses par catégorie (camembert) + tendance mensuelle (#113).

Les agrégations pures (`aggregate_expenses_by_category`, `month_keys`) sont testables
sans base ; les wrappers DB requêtent puis délèguent. Les dépenses sont les montants
négatifs ; on les renvoie en valeur absolue.
"""

from __future__ import annotations

import calendar
import csv
import datetime as dt
import io
import statistics
from typing import Any, Optional

UNCATEGORISED_COLOR = "#9aa3b0"


def aggregate_expenses_by_category(txs, cat_meta: dict[Optional[int], dict]) -> list[dict[str, Any]]:
    """Somme des dépenses (montant < 0, en valeur absolue) par catégorie, enrichie + triée desc."""
    by_cat: dict[Optional[int], float] = {}
    for t in txs:
        if t.montant < 0:
            by_cat[t.category_id] = by_cat.get(t.category_id, 0.0) + (-t.montant)
    total = sum(by_cat.values())
    out: list[dict[str, Any]] = []
    for cid, montant in by_cat.items():
        meta = cat_meta.get(cid)
        out.append({
            "category_id": cid,
            "nom": meta["nom"] if meta else "Sans catégorie",
            "couleur": meta["couleur"] if meta else UNCATEGORISED_COLOR,
            "montant": round(montant, 2),
            "pct": round(montant / total * 100, 1) if total > 0 else 0.0,
        })
    out.sort(key=lambda x: x["montant"], reverse=True)
    return out


def month_keys(today: dt.date, months: int) -> list[str]:
    """Les `months` derniers mois (YYYY-MM), du plus ancien au plus récent (incluant le courant)."""
    keys: list[str] = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(keys))


def detect_recurring(
    txs, *, min_occurrences: int = 3, amount_tolerance: float = 0.15
) -> list[dict[str, Any]]:
    """Détecte les dépenses récurrentes (abonnements) : même marchand, montant
    stable (±`amount_tolerance`) et cadence ~mensuelle (#116). Pur."""
    groups: dict[str, list] = {}
    for t in txs:
        if t.montant >= 0:
            continue
        key = (t.marchand or "").strip().lower()
        if key:
            groups.setdefault(key, []).append(t)

    out: list[dict[str, Any]] = []
    for items in groups.values():
        if len(items) < min_occurrences:
            continue
        items.sort(key=lambda t: t.date)
        amounts = [abs(t.montant) for t in items]
        avg = sum(amounts) / len(amounts)
        if avg <= 0 or any(abs(a - avg) / avg > amount_tolerance for a in amounts):
            continue  # montant instable -> pas un abonnement
        gaps = [(items[i + 1].date - items[i].date).days for i in range(len(items) - 1)]
        med_gap = statistics.median(gaps)
        if not (26 <= med_gap <= 35):
            continue  # cadence non mensuelle
        out.append({
            "marchand": items[0].marchand,
            "montant_moyen": round(avg, 2),
            "occurrences": len(items),
            "periodicite": "mensuel",
            "derniere_date": items[-1].date.isoformat(),
            "category_id": items[-1].category_id,
        })
    out.sort(key=lambda r: r["montant_moyen"], reverse=True)
    return out


# ── Wrappers DB ───────────────────────────────────────────────────────

def spending_by_category(session, mois: str) -> list[dict[str, Any]]:
    from app.services.budget import categories as cat_svc
    from app.services.budget import transactions as tx_svc

    year, month = int(mois[:4]), int(mois[5:])
    start = dt.date(year, month, 1)
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    txs = tx_svc.get_transactions(session, from_date=start, to_date=end)
    cats = {c.id: {"nom": c.nom, "couleur": c.couleur} for c in cat_svc.get_categories(session)}
    return aggregate_expenses_by_category(txs, cats)


def build_annual_csv(txs, cat_names: dict[Optional[int], str]) -> str:
    """CSV des transactions (triées par date) pour déclaration/bilan annuel (#122). Pur."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Marchand", "Description", "Montant", "Categorie", "Compte"])
    for t in sorted(txs, key=lambda x: x.date):
        w.writerow([
            t.date.isoformat(),
            getattr(t, "marchand", "") or "",
            getattr(t, "description", "") or "",
            f"{t.montant:.2f}",
            cat_names.get(t.category_id, ""),
            getattr(t, "compte", "") or "",
        ])
    return buf.getvalue()


def annual_export(session, year: int) -> str:
    from app.services.budget import categories as cat_svc
    from app.services.budget import transactions as tx_svc
    txs = tx_svc.get_transactions(session, from_date=dt.date(year, 1, 1), to_date=dt.date(year, 12, 31))
    cats = {c.id: c.nom for c in cat_svc.get_categories(session)}
    return build_annual_csv(txs, cats)


def recurring_expenses(session) -> list[dict[str, Any]]:
    from app.services.budget import transactions as tx_svc
    return detect_recurring(tx_svc.get_transactions(session))


def spending_trend(session, months: int = 6, *, today: Optional[dt.date] = None) -> list[dict[str, Any]]:
    from app.services.budget import transactions as tx_svc

    today = today or dt.date.today()
    keys = month_keys(today, months)
    start = dt.date(int(keys[0][:4]), int(keys[0][5:]), 1)
    txs = tx_svc.get_transactions(session, from_date=start, to_date=today)
    agg = {k: {"revenus": 0.0, "depenses": 0.0} for k in keys}
    for t in txs:
        key = t.date.strftime("%Y-%m")
        if key in agg:
            if t.montant > 0:
                agg[key]["revenus"] += t.montant
            else:
                agg[key]["depenses"] += -t.montant
    return [
        {"mois": k, "revenus": round(agg[k]["revenus"], 2), "depenses": round(agg[k]["depenses"], 2)}
        for k in keys
    ]
