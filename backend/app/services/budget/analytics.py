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


def aggregate_expenses_by_tag(txs) -> list[dict[str, Any]]:
    """Somme des dépenses (montant<0) par tag, triée desc. Pur.

    Une transaction compte dans CHACUN de ses tags (les tags sont multiples) ;
    celles sans tag sont regroupées sous « Sans tag »."""
    by_tag: dict[str, float] = {}
    for t in txs:
        if t.montant >= 0:
            continue
        keys = (getattr(t, "tags", None) or []) or ["Sans tag"]
        for k in keys:
            by_tag[k] = by_tag.get(k, 0.0) + (-t.montant)
    total = sum(by_tag.values())
    out = [
        {"tag": k, "montant": round(v, 2),
         "pct": round(v / total * 100, 1) if total > 0 else 0.0}
        for k, v in by_tag.items()
    ]
    out.sort(key=lambda x: x["montant"], reverse=True)
    return out


def spending_by_tag(session, *, days: int = 365, today: Optional[dt.date] = None) -> list[dict[str, Any]]:
    """Dépenses par tag sur les `days` derniers jours glissants."""
    from app.services.budget import transactions as tx_svc
    end = today or dt.date.today()
    txs = tx_svc.get_transactions(session, from_date=end - dt.timedelta(days=days - 1), to_date=end)
    return aggregate_expenses_by_tag(txs)


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


def rolling_totals(txs, *, end: dt.date, days: int = 30) -> dict[str, Any]:
    """Revenus / dépenses / solde sur la fenêtre glissante des `days` derniers
    jours (incluse jusqu'à `end`). Pur. Dépenses en valeur absolue."""
    start = end - dt.timedelta(days=days - 1)
    rev = dep = 0.0
    for t in txs:
        if not (start <= t.date <= end):
            continue
        if t.montant > 0:
            rev += t.montant
        else:
            dep += -t.montant
    return {
        "revenus": round(rev, 2), "depenses": round(dep, 2), "solde": round(rev - dep, 2),
        "debut": start.isoformat(), "fin": end.isoformat(), "jours": days,
    }


def category_share_series(
    txs, cat_meta: dict[Optional[int], dict], *,
    end: dt.date, days: int = 180, step_days: int = 14, window: int = 30,
) -> dict[str, Any]:
    """Part (%) de chaque catégorie de dépenses au fil du temps, en fenêtre
    glissante de `window` jours, échantillonnée tous les `step_days` sur `days`.

    Pur. Renvoie `{categories: [{category_id, nom, couleur}], points: [{date,
    shares: {nom: pct}}]}`, catégories triées par dépense totale décroissante.
    """
    n = days // step_days + 1
    dates = sorted(end - dt.timedelta(days=step_days * i) for i in range(n))

    def _meta(cid):
        m = cat_meta.get(cid)
        return (m["nom"], m["couleur"]) if m else ("Sans catégorie", UNCATEGORISED_COLOR)

    expenses = [(t.date, _meta(t.category_id), -t.montant) for t in txs if t.montant < 0]
    points: list[dict[str, Any]] = []
    totals: dict[str, float] = {}
    colors: dict[str, str] = {}
    for d in dates:
        w_start = d - dt.timedelta(days=window - 1)
        by: dict[str, float] = {}
        for td, (nom, couleur), amt in expenses:
            if w_start <= td <= d:
                by[nom] = by.get(nom, 0.0) + amt
                colors[nom] = couleur
                totals[nom] = totals.get(nom, 0.0) + amt
        tot = sum(by.values())
        shares = {nom: round(amt / tot * 100, 1) for nom, amt in by.items()} if tot > 0 else {}
        points.append({"date": d.isoformat(), "shares": shares})

    # Retire les points de tête sans aucune dépense (avant le début des données),
    # pour que « dézoomer au maximum » n'affiche pas une longue zone vide.
    while len(points) > 1 and not points[0]["shares"]:
        points.pop(0)

    ordered = sorted(totals, key=lambda nom: -totals[nom])
    categories = [{"nom": nom, "couleur": colors[nom]} for nom in ordered]
    return {"categories": categories, "points": points}


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


def rolling_summary(session, *, days: int = 30, today: Optional[dt.date] = None) -> dict[str, Any]:
    """Revenus/dépenses/solde sur les `days` derniers jours glissants (#window)."""
    from app.services.budget import transactions as tx_svc
    end = today or dt.date.today()
    txs = tx_svc.get_transactions(session, from_date=end - dt.timedelta(days=days - 1), to_date=end)
    return rolling_totals(txs, end=end, days=days)


def category_share_timeseries(
    session, *, days: int = 180, window: int = 30, step_days: int = 14,
    today: Optional[dt.date] = None,
) -> dict[str, Any]:
    """Part (%) des catégories de dépenses au fil du temps (fenêtre glissante)."""
    from app.services.budget import categories as cat_svc
    from app.services.budget import transactions as tx_svc
    end = today or dt.date.today()
    start = end - dt.timedelta(days=days + window)
    txs = tx_svc.get_transactions(session, from_date=start, to_date=end)
    cats = {c.id: {"nom": c.nom, "couleur": c.couleur} for c in cat_svc.get_categories(session)}
    return category_share_series(txs, cats, end=end, days=days, window=window, step_days=step_days)


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


def recurring_vs_oneoff(txs, **kwargs) -> dict[str, Any]:
    """Sépare dépenses récurrentes (abonnements) vs ponctuelles + projection
    annuelle des récurrentes (#266). Pur.

    - `recurrent_mensuel_total`        : somme des abonnements mensuels détectés
    - `projection_annuelle_recurrents` : ×12
    - `ponctuel_total`                 : dépenses non récurrentes sur la période
    """
    recurring = detect_recurring(txs, **kwargs)
    rec_keys = {(r["marchand"] or "").strip().lower() for r in recurring}
    rec_monthly = sum(r["montant_moyen"] for r in recurring)
    oneoff = sum(
        abs(t.montant) for t in txs
        if t.montant < 0 and (getattr(t, "marchand", "") or "").strip().lower() not in rec_keys
    )
    return {
        "recurrents": recurring,
        "nb_recurrents": len(recurring),
        "recurrent_mensuel_total": round(rec_monthly, 2),
        "projection_annuelle_recurrents": round(rec_monthly * 12, 2),
        "ponctuel_total": round(oneoff, 2),
    }


def recurring_expenses(session) -> list[dict[str, Any]]:
    from app.services.budget import transactions as tx_svc
    return detect_recurring(tx_svc.get_transactions(session))


def recurring_summary(session) -> dict[str, Any]:
    from app.services.budget import transactions as tx_svc
    return recurring_vs_oneoff(tx_svc.get_transactions(session))


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
    out = [
        {"mois": k, "revenus": round(agg[k]["revenus"], 2), "depenses": round(agg[k]["depenses"], 2)}
        for k in keys
    ]
    # Retire les mois de tête vides (avant le début des données) pour le dézoom.
    while len(out) > 1 and out[0]["revenus"] == 0 and out[0]["depenses"] == 0:
        out.pop(0)
    return out
