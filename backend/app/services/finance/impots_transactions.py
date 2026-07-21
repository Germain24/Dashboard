"""Calcul fiscal des transactions de valeurs mobilieres.

Pour les titres fongibles, le prix d'acquisition fiscal est le prix moyen
pondere (PMP), calcule compte par compte. Les transactions doivent etre
stockees en EUR au taux de l'operation ; une devise etrangere sans montant EUR
historique est signalee et exclue plutot que convertie au cours du jour.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _to_eur_per_unit(prix: float, devise: str | None) -> float:
    """Convertit un prix natif vers EUR pour les imports historiques PDF.

    Trading 212 exprime les instruments londoniens en GBX (pence). Le CSV
    complet reste preferable car sa colonne Total contient la conversion de
    l'operation ; ce helper maintient le chemin PDF historique fonctionnel.
    """
    from app.services.finance.fx import convert

    currency = (devise or "EUR").upper()
    if currency == "GBX":
        return convert(prix / 100, "GBP", "EUR")
    return convert(prix, currency, "EUR")


def _sort_key(transaction: Any) -> tuple:
    return transaction.date, getattr(transaction, "id", 0) or 0


def _account_key(transaction: Any) -> tuple[str, str]:
    ticker = str(getattr(transaction, "ticker", "") or "").upper()
    broker = str(getattr(transaction, "broker", "") or "default").casefold()
    return ticker, broker


def _is_eur(transaction: Any) -> bool:
    return str(getattr(transaction, "devise", "EUR") or "EUR").upper() == "EUR"


def compute_realized_sales_pmp(transactions: list[Any]) -> list[dict]:
    """Renvoie une ligne par vente avec un cout d'acquisition au PMP.

    Une vente sans stock d'achat suffisant reste visible avec
    ``calculable=False``. Elle n'entre pas dans le gain annuel afin de ne pas
    fabriquer une assiette fiscale fausse.
    """
    books: dict[tuple[str, str], dict[str, float | bool]] = defaultdict(
        lambda: {"quantite": 0.0, "cout": 0.0, "devise_invalide": False}
    )
    sales: list[dict] = []

    for transaction in sorted(transactions, key=_sort_key):
        kind = str(getattr(transaction, "type", "") or "").lower()
        if kind not in ("achat", "vente"):
            continue

        ticker, broker_key = _account_key(transaction)
        broker = getattr(transaction, "broker", None) or "default"
        quantity = float(getattr(transaction, "quantite", 0) or 0)
        unit_price = float(getattr(transaction, "prix_unitaire", 0) or 0)
        fees = float(getattr(transaction, "frais", 0) or 0)
        book = books[(ticker, broker_key)]

        if kind == "achat":
            if quantity <= 0:
                continue
            if not _is_eur(transaction):
                book["devise_invalide"] = True
                continue
            book["quantite"] = float(book["quantite"]) + quantity
            book["cout"] = float(book["cout"]) + quantity * unit_price + fees
            continue

        reason: str | None = None
        available = float(book["quantite"])
        if quantity <= 0:
            reason = "Quantite de vente invalide"
        elif not _is_eur(transaction) or bool(book["devise_invalide"]):
            reason = "Conversion EUR historique manquante"
        elif available + 1e-8 < quantity:
            reason = "Historique d'achat incomplet"

        pmp = float(book["cout"]) / available if available > 1e-9 else 0.0
        if reason is not None:
            sales.append({
                "date": transaction.date,
                "ticker": ticker,
                "broker": broker,
                "quantite": round(quantity, 6),
                "prix_achat_moyen": round(pmp, 4),
                "prix_vente": round(unit_price, 4),
                "produit_net": None,
                "cout_acquisition": None,
                "frais_vente": round(fees, 2),
                "plus_value": None,
                "calculable": False,
                "raison": reason,
            })
            continue

        acquisition_cost = pmp * quantity
        net_proceeds = unit_price * quantity - fees
        realized = net_proceeds - acquisition_cost
        book["quantite"] = max(0.0, available - quantity)
        book["cout"] = max(0.0, float(book["cout"]) - acquisition_cost)
        if float(book["quantite"]) <= 1e-8:
            book["quantite"] = 0.0
            book["cout"] = 0.0

        sales.append({
            "date": transaction.date,
            "ticker": ticker,
            "broker": broker,
            "quantite": round(quantity, 6),
            "prix_achat_moyen": round(pmp, 4),
            "prix_vente": round(unit_price, 4),
            "produit_net": round(net_proceeds, 2),
            "cout_acquisition": round(acquisition_cost, 2),
            "frais_vente": round(fees, 2),
            "plus_value": round(realized, 2),
            "calculable": True,
            "raison": None,
        })

    return sales


def compute_realized_gains_pmp(transactions: list[Any]) -> dict[int, float]:
    gains_by_year: dict[int, float] = defaultdict(float)
    for sale in compute_realized_sales_pmp(transactions):
        if sale["calculable"]:
            gains_by_year[sale["date"].year] += float(sale["plus_value"])
    return {year: round(gain, 2) for year, gain in gains_by_year.items()}


# Compatibilite temporaire avec les imports internes et les extensions locales.
compute_realized_sales_fifo = compute_realized_sales_pmp
compute_realized_gains_fifo = compute_realized_gains_pmp


def _ledger_transactions(session, *, broker: str | None = None) -> list[Any]:
    from sqlmodel import select

    from app.models.finance import Transaction

    stmt = select(Transaction).where(Transaction.type.in_(["achat", "vente"]))
    if broker:
        stmt = stmt.where(Transaction.broker == broker)
    return list(session.exec(stmt).all())


def realized_sales_detail(
    session, *, broker: str | None = None, annee: int | None = None,
) -> list[dict]:
    sales = compute_realized_sales_pmp(_ledger_transactions(session, broker=broker))
    if annee is not None:
        sales = [sale for sale in sales if sale["date"].year == annee]
    return sorted(sales, key=lambda sale: sale["date"], reverse=True)


def realized_gains_by_year(session, *, broker: str | None = None) -> dict[int, float]:
    return compute_realized_gains_pmp(_ledger_transactions(session, broker=broker))


def investment_income_by_year(
    session, *, broker: str | None = None,
) -> tuple[dict[int, dict[str, float]], dict[int, int]]:
    """Revenus mobiliers par annee et nombre de lignes non converties en EUR."""
    from sqlmodel import select

    from app.models.finance import Transaction

    stmt = select(Transaction).where(Transaction.type.in_(["dividende", "interet"]))
    if broker:
        stmt = stmt.where(Transaction.broker == broker)
    result: dict[int, dict[str, float]] = defaultdict(
        lambda: {
            "dividendes_bruts": 0.0,
            "dividendes_eligibles_bruts": 0.0,
            "dividendes_nets": 0.0,
            "interets_bruts": 0.0,
            "interets_nets": 0.0,
            "retenue_source": 0.0,
        }
    )
    excluded: dict[int, int] = defaultdict(int)
    for transaction in session.exec(stmt).all():
        if not _is_eur(transaction):
            excluded[transaction.date.year] += 1
            continue
        fallback = float(transaction.quantite or 0) * float(transaction.prix_unitaire or 0)
        gross = getattr(transaction, "montant_brut", None)
        gross = float(gross) if gross is not None else fallback
        withholding = float(getattr(transaction, "retenue_source", 0) or 0)
        fees = float(transaction.frais or 0)
        year = transaction.date.year
        if transaction.type == "interet":
            result[year]["interets_bruts"] += gross
            result[year]["interets_nets"] += gross - fees
            continue
        result[year]["dividendes_bruts"] += gross
        if "manufactured" not in str(transaction.note or "").casefold():
            result[year]["dividendes_eligibles_bruts"] += gross
        result[year]["retenue_source"] += withholding
        result[year]["dividendes_nets"] += gross - withholding - fees
    rounded = {
        year: {key: round(value, 2) for key, value in row.items()}
        for year, row in result.items()
    }
    return rounded, dict(excluded)


def dividends_by_year(session, *, broker: str | None = None) -> dict[int, dict[str, float]]:
    """Alias structure pour les extensions locales historiques."""
    rows, _ = investment_income_by_year(session, broker=broker)
    return rows


def compute_tax_summary(
    session,
    *,
    annee: int,
    autres_revenus: float = 0.0,
    parts: float = 1.0,
    moins_values_anterieures: float = 0.0,
    moins_values_anterieures_annee: int | None = None,
    dividendes_eligibles_abattement: bool = True,
    broker: str | None = None,
) -> dict:
    from app.services.finance.impots import (
        bareme_for_income_year,
        compare_regimes,
        social_rate_for_income_year,
    )

    transactions = _ledger_transactions(session, broker=broker)
    sales = compute_realized_sales_pmp(transactions)
    gains: dict[int, float] = defaultdict(float)
    for sale in sales:
        if sale["calculable"] and sale["date"].year <= annee:
            gains[sale["date"].year] += float(sale["plus_value"])
    gains = {year: round(value, 2) for year, value in gains.items()}
    years = sorted({year for year in gains if year <= annee} | {annee})

    origin = moins_values_anterieures_annee or annee - 1
    vintages: list[list[float | int]] = []

    net_year = 0.0
    history: dict[int, dict] = {}
    for year in years:
        vintages = [vintage for vintage in vintages if year - int(vintage[0]) <= 10]
        # La saisie manuelle represente un report disponible au debut de
        # l'annee demandee. Elle ne doit jamais effacer retroactivement un
        # gain deja realise dans l'historique du ledger.
        if (
            year == annee
            and moins_values_anterieures > 0
            and annee - origin <= 10
        ):
            vintages.append([origin, moins_values_anterieures])
            vintages.sort(key=lambda vintage: int(vintage[0]))
        gain = gains.get(year, 0.0)
        if gain <= 0:
            vintages.append([year, -gain])
            net = 0.0
        else:
            remaining = gain
            for vintage in vintages:
                if remaining <= 0:
                    break
                offset = min(remaining, float(vintage[1]))
                vintage[1] = float(vintage[1]) - offset
                remaining -= offset
            vintages = [vintage for vintage in vintages if float(vintage[1]) > 1e-9]
            net = round(remaining, 2)
        history[year] = {
            "gain_brut": gain,
            "gain_net_imposable": net,
            "report_apres": round(sum(float(vintage[1]) for vintage in vintages), 2),
        }
        if year == annee:
            net_year = net

    vintages = [vintage for vintage in vintages if annee - int(vintage[0]) <= 10]
    report = round(sum(float(vintage[1]) for vintage in vintages), 2)
    income_by_year, excluded_income = investment_income_by_year(
        session, broker=broker
    )
    income = income_by_year.get(
        annee,
        {
            "dividendes_bruts": 0.0,
            "dividendes_eligibles_bruts": 0.0,
            "dividendes_nets": 0.0,
            "interets_bruts": 0.0,
            "interets_nets": 0.0,
            "retenue_source": 0.0,
        },
    )
    regimes = compare_regimes(
        autres_revenus,
        net_year,
        parts,
        annee=annee,
        dividendes_bruts=income["dividendes_bruts"],
        dividendes_eligibles_abattement=dividendes_eligibles_abattement,
        dividendes_eligibles_bruts=income["dividendes_eligibles_bruts"],
        interets_bruts=income["interets_bruts"],
    )
    _, bareme_reference, bareme_provisoire = bareme_for_income_year(annee)
    incomplete = [sale for sale in sales if not sale["calculable"] and sale["date"].year <= annee]

    warnings: list[str] = []
    if incomplete:
        warnings.append(
            f"{len(incomplete)} vente(s) exclue(s) : historique d'achat ou conversion EUR incomplet."
        )
    excluded_income_total = sum(
        count for year, count in excluded_income.items() if year <= annee
    )
    if excluded_income_total:
        warnings.append(
            f"{excluded_income_total} revenu(s) mobilier(s) exclu(s) : conversion EUR historique manquante."
        )
    if income["retenue_source"] > 0:
        warnings.append(
            "La retenue etrangere est affichee separement ; son credit d'impot depend de la convention fiscale."
        )
    non_eligible_dividends = round(
        income["dividendes_bruts"] - income["dividendes_eligibles_bruts"], 2
    )
    if non_eligible_dividends > 0:
        warnings.append(
            f"{non_eligible_dividends:.2f} EUR de paiement(s) compensatoire(s) de dividende sont exclus de l'abattement de 40 %."
        )
    if bareme_provisoire:
        warnings.append(
            f"Le bareme de l'annee {annee} n'est pas encore publie ; estimation avec le bareme des revenus {bareme_reference}."
        )

    return {
        "annee": annee,
        "methode_cout": "PMP",
        "gain_brut": round(gains.get(annee, 0.0), 2),
        "gain_net_imposable": net_year,
        "report_moins_values_restant": report,
        "dividendes_bruts": income["dividendes_bruts"],
        "dividendes_eligibles_bruts": income["dividendes_eligibles_bruts"],
        "dividendes_nets": income["dividendes_nets"],
        "interets_bruts": income["interets_bruts"],
        "interets_nets": income["interets_nets"],
        "revenus_mobiliers_bruts": round(
            income["dividendes_bruts"] + income["interets_bruts"], 2
        ),
        "revenus_mobiliers_nets": round(
            income["dividendes_nets"] + income["interets_nets"], 2
        ),
        "retenue_source_etrangere": income["retenue_source"],
        "historique_par_annee": history,
        "taux_sociaux_pct": round(social_rate_for_income_year(annee) * 100, 1),
        "bareme_reference_revenus": bareme_reference,
        "bareme_provisoire": bareme_provisoire,
        "dividendes_eligibles_abattement": dividendes_eligibles_abattement,
        "data_quality": {
            "ventes_total": sum(1 for sale in sales if sale["date"].year == annee),
            "ventes_calculables": sum(
                1 for sale in sales if sale["date"].year == annee and sale["calculable"]
            ),
            "ventes_exclues": sum(
                1 for sale in sales if sale["date"].year == annee and not sale["calculable"]
            ),
            "revenus_exclus": excluded_income.get(annee, 0),
        },
        "avertissements": warnings,
        **regimes,
    }
