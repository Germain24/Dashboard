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


def _monthly_cadence_groups(txs, *, min_occurrences: int = 3) -> list[list]:
    """Groupes de dépenses d'un même marchand à cadence ~mensuelle, triés par date.

    Brique partagée par `detect_recurring` (#116) et les alertes d'abonnement
    (#260) : seule la cadence est vérifiée ici, PAS la stabilité du montant —
    une hausse de prix doit rester détectable même quand elle fait sortir
    l'abonnement du filtre de stabilité.
    """
    groups: dict[str, list] = {}
    for t in txs:
        if t.montant >= 0:
            continue
        key = (t.marchand or "").strip().lower()
        if key:
            groups.setdefault(key, []).append(t)

    out: list[list] = []
    for items in groups.values():
        if len(items) < min_occurrences:
            continue
        items.sort(key=lambda t: t.date)
        gaps = [(items[i + 1].date - items[i].date).days for i in range(len(items) - 1)]
        if 26 <= statistics.median(gaps) <= 35:
            out.append(items)
    return out


def _amounts_are_stable(amounts: list[float], tolerance: float) -> bool:
    """Vrai si tous les montants tiennent dans ±`tolerance` de leur moyenne."""
    avg = sum(amounts) / len(amounts) if amounts else 0.0
    return avg > 0 and all(abs(a - avg) / avg <= tolerance for a in amounts)


def detect_recurring(
    txs, *, min_occurrences: int = 3, amount_tolerance: float = 0.15
) -> list[dict[str, Any]]:
    """Détecte les dépenses récurrentes (abonnements) : même marchand, montant
    stable (±`amount_tolerance`) et cadence ~mensuelle (#116). Pur."""
    out: list[dict[str, Any]] = []
    for items in _monthly_cadence_groups(txs, min_occurrences=min_occurrences):
        amounts = [abs(t.montant) for t in items]
        if not _amounts_are_stable(amounts, amount_tolerance):
            continue  # montant instable -> pas un abonnement
        avg = sum(amounts) / len(amounts)
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


# ─── Alertes sur abonnements : hausses de prix & doublons (#260) ─────────────

# Une hausse n'est signalée que si elle franchit À LA FOIS un plancher absolu et
# un plancher relatif : l'absolu écarte les arrondis et écarts de change de
# quelques centimes, le relatif écarte les micro-ajustements (taxes) sur les gros
# montants. Fenêtre de comparaison de 13 mois : le prix d'il y a deux ans ne doit
# plus déclencher d'alerte aujourd'hui.
HAUSSE_MIN_ABS = 1.0
HAUSSE_MIN_PCT = 5.0
HAUSSE_FENETRE_JOURS = 395

# Passerelles de paiement / places de marché : leur nom occupe le 1er token du
# libellé (« PAYPAL *NETFLIX »), donc deux abonnements sans rapport y partagent
# la même clé de service. Jamais un doublon sur ces clés-là.
_PASSERELLES = frozenset({
    "PAYPAL", "SQUARE", "STRIPE", "GOOGLE", "APPLE", "ITUNES", "AMAZON", "AMZN",
    "MICROSOFT", "MSFT", "SHOPIFY", "PADDLE", "VISA", "MASTERCARD", "INTERAC",
    "ACHAT", "PAIEMENT", "PRELEVEMENT", "PRLV", "RETRAIT", "VIREMENT",
})


def _service_key(marchand: Optional[str]) -> Optional[str]:
    """Clé de service d'un libellé bancaire (même normalisation que les règles)."""
    from app.services.budget.rules import merchant_key
    return merchant_key(marchand or "")


def detect_price_increases(
    txs, *, min_occurrences: int = 3, min_abs: float = HAUSSE_MIN_ABS,
    min_pct: float = HAUSSE_MIN_PCT, fenetre_jours: int = HAUSSE_FENETRE_JOURS,
) -> list[dict[str, Any]]:
    """Abonnements dont le prix a augmenté par rapport à leur propre historique. Pur.

    Compare le dernier prélèvement à la MÉDIANE des précédents (robuste à un
    prélèvement aberrant isolé), sur la fenêtre des `fenetre_jours` derniers
    jours du marchand. Volontairement basé sur la cadence seule, pas sur
    `detect_recurring` : une forte hausse rend le montant « instable » et
    ferait justement disparaître l'abonnement du filtre de stabilité.
    """
    out: list[dict[str, Any]] = []
    for items in _monthly_cadence_groups(txs, min_occurrences=min_occurrences):
        cutoff = items[-1].date - dt.timedelta(days=fenetre_jours)
        recents = [t for t in items if t.date >= cutoff]
        if len(recents) < max(3, min_occurrences):
            continue  # il faut au moins 2 prélèvements de référence + le dernier
        actuel = abs(recents[-1].montant)
        precedent = statistics.median(abs(t.montant) for t in recents[:-1])
        delta = actuel - precedent
        if precedent <= 0 or delta < min_abs or delta / precedent * 100 < min_pct:
            continue
        out.append({
            "marchand": recents[-1].marchand,
            "montant_precedent": round(precedent, 2),
            "montant_actuel": round(actuel, 2),
            "delta": round(delta, 2),
            "delta_pct": round(delta / precedent * 100, 1),
            "date": recents[-1].date.isoformat(),
            "occurrences": len(recents),
            "category_id": recents[-1].category_id,
        })
    out.sort(key=lambda h: h["delta"], reverse=True)
    return out


def detect_duplicate_subscriptions(
    txs, *, min_occurrences: int = 3, amount_tolerance: float = 0.15,
    doublon_tolerance: float = 0.10,
) -> list[dict[str, Any]]:
    """Abonnements vraisemblablement payés en double (#260). Pur.

    Deux familles, toutes deux volontairement conservatrices — sur des données
    bancaires réelles un faux doublon coûte plus cher qu'un oubli :

    - `double_prelevement` : le même marchand débité ≥2× dans le même mois
      calendaire, chaque fois AU PRIX de l'abonnement (±`doublon_tolerance`).
      Exiger le prix de l'abonnement écarte les marchands simplement fréquents.
    - `meme_service` : deux marchands récurrents distincts partageant la même clé
      de service, à un prix comparable (±`amount_tolerance`) et prélevés au moins
      un mois EN COMMUN. Le mois commun est décisif : sans lui, un simple
      changement de libellé bancaire (« NETFLIX » → « NETFLIX.COM ») serait
      signalé comme un doublon alors que c'est le même abonnement qui continue.
    """
    groups = _monthly_cadence_groups(txs, min_occurrences=min_occurrences)
    out: list[dict[str, Any]] = []

    for items in groups:
        median_amt = statistics.median(abs(t.montant) for t in items)
        if median_amt <= 0:
            continue
        by_month: dict[str, list[float]] = {}
        for t in items:
            by_month.setdefault(t.date.strftime("%Y-%m"), []).append(abs(t.montant))
        for mois, amounts in sorted(by_month.items()):
            au_prix = [a for a in amounts if abs(a - median_amt) / median_amt <= doublon_tolerance]
            if len(au_prix) < 2:
                continue
            out.append({
                "type": "double_prelevement",
                "service": _service_key(items[0].marchand) or items[0].marchand,
                "marchands": [items[0].marchand],
                "mois": mois,
                "occurrences": len(au_prix),
                "montant_redondant": round(median_amt * (len(au_prix) - 1), 2),
            })

    mois_par_marchand: dict[str, set[str]] = {}
    for t in txs:
        key = (getattr(t, "marchand", "") or "").strip().lower()
        if t.montant < 0 and key:
            mois_par_marchand.setdefault(key, set()).add(t.date.strftime("%Y-%m"))

    par_service: dict[str, list[dict[str, Any]]] = {}
    for s in detect_recurring(txs, min_occurrences=min_occurrences,
                              amount_tolerance=amount_tolerance):
        key = _service_key(s["marchand"])
        if key and key not in _PASSERELLES:
            par_service.setdefault(key, []).append(s)

    for service, membres in par_service.items():
        if len(membres) < 2:
            continue
        membres.sort(key=lambda s: s["montant_moyen"], reverse=True)
        for i, a in enumerate(membres):
            for b in membres[i + 1:]:
                hi, lo = a["montant_moyen"], b["montant_moyen"]
                if lo <= 0 or (hi - lo) / hi > amount_tolerance:
                    continue  # prix trop éloignés -> deux services différents
                communs = (mois_par_marchand.get(a["marchand"].strip().lower(), set())
                           & mois_par_marchand.get(b["marchand"].strip().lower(), set()))
                if not communs:
                    continue  # jamais prélevés le même mois -> libellé renommé
                out.append({
                    "type": "meme_service",
                    "service": service,
                    "marchands": [a["marchand"], b["marchand"]],
                    "mois": max(communs),
                    "occurrences": len(communs),
                    "montant_redondant": round(lo, 2),
                })

    out.sort(key=lambda d: d["montant_redondant"], reverse=True)
    return out


def subscription_alerts(
    txs, *, min_occurrences: int = 3, amount_tolerance: float = 0.15,
    hausse_min_abs: float = HAUSSE_MIN_ABS, hausse_min_pct: float = HAUSSE_MIN_PCT,
) -> dict[str, Any]:
    """Alertes sur les abonnements détectés : hausses de prix + doublons (#260). Pur.

    `surcout_mensuel` = ce que ces alertes coûtent par mois (hausses subies +
    prélèvements redondants), c'est-à-dire l'économie potentielle.
    """
    hausses = detect_price_increases(
        txs, min_occurrences=min_occurrences,
        min_abs=hausse_min_abs, min_pct=hausse_min_pct,
    )
    doublons = detect_duplicate_subscriptions(
        txs, min_occurrences=min_occurrences, amount_tolerance=amount_tolerance,
    )
    surcout = sum(h["delta"] for h in hausses) + sum(d["montant_redondant"] for d in doublons)
    return {
        "hausses": hausses,
        "doublons": doublons,
        "nb_alertes": len(hausses) + len(doublons),
        "surcout_mensuel": round(surcout, 2),
    }


def subscription_alerts_summary(session) -> dict[str, Any]:
    from app.services.budget import transactions as tx_svc
    return subscription_alerts(tx_svc.get_transactions(session))


def cash_flow_forecast(
    monthly_history: list[dict[str, Any]], *,
    months_ahead: int = 6, scenario: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """Prévision de trésorerie (#259) : projette le solde net mensuel sur
    `months_ahead` mois à partir de la moyenne revenus/dépenses des mois
    historiques fournis (ex. `spending_trend`). Pur.

    `scenario` ajuste la moyenne en % : {"revenus_delta_pct": 10,
    "depenses_delta_pct": -5} simule +10% de revenus et -5% de dépenses.
    """
    if not monthly_history:
        return {
            "moyenne_revenus": 0.0, "moyenne_depenses": 0.0,
            "solde_mensuel_moyen": 0.0, "points": [],
        }
    scenario = scenario or {}
    avg_rev = sum(m["revenus"] for m in monthly_history) / len(monthly_history)
    avg_dep = sum(m["depenses"] for m in monthly_history) / len(monthly_history)
    avg_rev *= 1 + scenario.get("revenus_delta_pct", 0.0) / 100
    avg_dep *= 1 + scenario.get("depenses_delta_pct", 0.0) / 100
    solde_mensuel = avg_rev - avg_dep

    y, m = (int(x) for x in monthly_history[-1]["mois"].split("-"))
    points: list[dict[str, Any]] = []
    cumul = 0.0
    for _ in range(months_ahead):
        m += 1
        if m > 12:
            m, y = 1, y + 1
        cumul += solde_mensuel
        points.append({
            "mois": f"{y:04d}-{m:02d}",
            "solde_mensuel": round(solde_mensuel, 2),
            "cumul": round(cumul, 2),
        })
    return {
        "moyenne_revenus": round(avg_rev, 2),
        "moyenne_depenses": round(avg_dep, 2),
        "solde_mensuel_moyen": round(solde_mensuel, 2),
        "points": points,
    }


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


def cash_flow_projection(
    session, *, months_ahead: int = 6, history_months: int = 6,
    scenario: Optional[dict[str, float]] = None, today: Optional[dt.date] = None,
) -> dict[str, Any]:
    """Prévision de trésorerie (#259) basée sur la tendance des `history_months`
    derniers mois réels (`spending_trend`)."""
    history = spending_trend(session, history_months, today=today)
    return cash_flow_forecast(history, months_ahead=months_ahead, scenario=scenario)
