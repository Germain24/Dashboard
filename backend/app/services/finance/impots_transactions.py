"""Plus/moins-values réalisées par année, calculées en FIFO depuis le grand
livre des transactions (`app.models.finance.Transaction`).

FIFO par ticker : chaque vente consomme les lots d'achat les plus anciens en
premier (méthode retenue par l'administration fiscale française à défaut de
justificatif contraire). Conversion en EUR au taux du jour (best-effort,
cohérent avec le reste du code — `patrimoine.to_eur`, `voyage._prix_en_eur` —
qui n'utilise pas non plus de taux FX historique daté). GBX (pence
sterling, Trading212) est divisé par 100 avant conversion GBP→EUR.

`t.frais` (frais de transaction) entre dans le calcul de la plus-value :
à l'achat, il est réparti sur les unités achetées et vient augmenter le
coût de base par unité du lot ; à la vente, il réduit le produit net de la
cession (une seule fois par vente, quel que soit le nombre de lots FIFO
consommés).

`compute_realized_gains_fifo` est pur sur une liste de transactions déjà
chargée (testable sans DB) ; `realized_gains_by_year` lit la DB.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict, deque
from typing import Any


def _to_eur_per_unit(prix: float, devise: str | None) -> float:
    from app.services.finance.fx import convert
    devise = (devise or "EUR").upper()
    if devise == "GBX":  # pence sterling -> livres -> EUR
        return convert(prix / 100, "GBP", "EUR")
    return convert(prix, devise, "EUR")


def compute_realized_sales_fifo(transactions: list[Any]) -> list[dict]:
    """Détail VENTE PAR VENTE (FIFO) : une ligne par vente, dans l'ordre
    chronologique -- `compute_realized_gains_fifo` s'obtient en agrégeant ces
    lignes par année (cf. plus bas), pour un tableau "date, ticker, prix
    d'achat moyen, prix de vente, plus-value" par cession.

    `transactions` : objets avec `.date` (datetime), `.ticker`, `.type`
    ("achat"/"vente"), `.quantite`, `.prix_unitaire`, `.devise`, `.frais`
    (frais de transaction, en `devise`, ajusté le coût de base à l'achat et
    réduit le produit net à la vente). Une vente à découvert (rien à
    consommer) n'a pas de coût de base connu -> ignorée
    (best-effort). `prix_achat_moyen` est la moyenne pondérée des lots FIFO
    consommés par CETTE vente (peut mélanger plusieurs achats à prix
    différents si la vente dépasse le lot le plus ancien). L'impôt PFU
    (30 %, taux plein -- l'imputation des moins-values antérieures se fait au
    niveau ANNUEL, pas ligne par ligne, cf. `compute_tax_summary`) est estimé
    par ligne pour une lecture directe, uniquement informative sur une
    plus-value isolée."""
    from app.services.finance.impots import PFU_RATE

    lots: dict[str, deque[list[float]]] = defaultdict(deque)  # ticker -> [[qty, cost_eur], ...]
    sales: list[dict] = []

    for t in sorted(transactions, key=lambda t: t.date):
        if t.type not in ("achat", "vente"):
            continue
        prix_eur = _to_eur_per_unit(t.prix_unitaire, t.devise)
        queue = lots[t.ticker]
        if t.type == "achat":
            frais_eur = _to_eur_per_unit(t.frais or 0.0, t.devise)
            cout_unitaire = prix_eur + (frais_eur / t.quantite if t.quantite else 0.0)
            queue.append([t.quantite, cout_unitaire])
            continue
        qty_to_sell = t.quantite
        realized = 0.0
        cout_total = 0.0
        qty_vendue = 0.0
        while qty_to_sell > 1e-9 and queue:
            lot = queue[0]
            sold = min(qty_to_sell, lot[0])
            realized += sold * (prix_eur - lot[1])
            cout_total += sold * lot[1]
            qty_vendue += sold
            lot[0] -= sold
            qty_to_sell -= sold
            if lot[0] <= 1e-9:
                queue.popleft()
        if qty_vendue <= 1e-9:
            continue
        frais_eur = _to_eur_per_unit(t.frais or 0.0, t.devise)
        realized -= frais_eur
        plus_value = round(realized, 2)
        sales.append({
            "date": t.date,
            "ticker": t.ticker,
            "quantite": round(qty_vendue, 6),
            "prix_achat_moyen": round(cout_total / qty_vendue, 4),
            "prix_vente": round(prix_eur, 4),
            "plus_value": plus_value,
            "impot_estime_pfu": round(max(0.0, plus_value) * PFU_RATE, 2),
        })
    return sales


def compute_realized_gains_fifo(transactions: list[Any]) -> dict[int, float]:
    """`{année: gain_net_realise_eur}` (positif = plus-value, négatif =
    moins-value), agrégé depuis `compute_realized_sales_fifo`."""
    gains_by_year: dict[int, float] = defaultdict(float)
    for sale in compute_realized_sales_fifo(transactions):
        gains_by_year[sale["date"].year] += sale["plus_value"]
    return {y: round(g, 2) for y, g in gains_by_year.items()}


def realized_sales_detail(session, *, broker: str | None = None, annee: int | None = None) -> list[dict]:
    """Lit le grand livre des transactions et renvoie le détail vente par
    vente (FIFO), le plus récent en premier. `annee` filtre sur l'année de la
    VENTE (pas des achats, qui peuvent être antérieurs)."""
    from sqlmodel import select
    from app.models.finance import Transaction

    stmt = select(Transaction).where(Transaction.type.in_(["achat", "vente"]))
    if broker:
        stmt = stmt.where(Transaction.broker == broker)
    txs = session.exec(stmt).all()
    sales = compute_realized_sales_fifo(txs)
    if annee is not None:
        sales = [s for s in sales if s["date"].year == annee]
    return sorted(sales, key=lambda s: s["date"], reverse=True)


def realized_gains_by_year(session, *, broker: str | None = None) -> dict[int, float]:
    """Lit le grand livre des transactions (optionnellement filtré par
    broker) et calcule les plus/moins-values réalisées par année (FIFO)."""
    from sqlmodel import select
    from app.models.finance import Transaction

    stmt = select(Transaction).where(Transaction.type.in_(["achat", "vente"]))
    if broker:
        stmt = stmt.where(Transaction.broker == broker)
    txs = session.exec(stmt).all()
    return compute_realized_gains_fifo(txs)


def compute_tax_summary(
    session, *, annee: int, autres_revenus: float = 0.0, parts: float = 1.0,
    moins_values_anterieures: float = 0.0, broker: str | None = None,
) -> dict:
    """Vue complète pour l'onglet Impôts : plus-value réalisée de `annee`
    (FIFO depuis les transactions), report de moins-values imputé
    chronologiquement depuis `moins_values_anterieures` (solde AVANT
    l'historique connu du grand livre) à travers toutes les années
    disponibles jusqu'à `annee` incluse, puis comparaison PFU / barème
    progressif sur le gain net résultant.

    Le report est suivi par "vintage" (année d'origine, montant restant) au
    lieu d'un simple solde roulant : chaque perte expire 10 ans après son
    année d'origine (jamais au-delà, cf. `impots.py`), et l'imputation
    consomme les vintages les plus anciens en premier (les plus proches de
    l'expiration)."""
    from app.services.finance.impots import compare_regimes

    gains = realized_gains_by_year(session, broker=broker)
    annees = sorted(y for y in gains if y <= annee)

    # Le solde "anterieur" fourni par l'appelant (avant le debut du grand
    # livre connu) est traite comme originaire de l'annee juste avant la
    # premiere annee connue -- il expire donc lui aussi au bout de 10 ans
    # comme n'importe quel autre vintage, au lieu de rester eternellement
    # valide.
    premiere_annee_connue = annees[0] if annees else annee
    vintages: list[list] = []  # [[origin_year, montant_restant], ...] ordre croissant = plus ancien d'abord
    if moins_values_anterieures > 0:
        vintages.append([premiere_annee_connue - 1, moins_values_anterieures])

    net_annee = 0.0
    par_annee: dict[int, dict] = {}
    for y in annees:
        vintages = [v for v in vintages if y - v[0] <= 10]  # purge expiration
        gain = gains[y]
        if gain <= 0:
            vintages.append([y, -gain])
            net = 0.0
        else:
            restant = gain
            for v in vintages:  # plus ancien d'abord (liste deja triee par construction)
                if restant <= 0:
                    break
                impute = min(restant, v[1])
                v[1] -= impute
                restant -= impute
            vintages = [v for v in vintages if v[1] > 1e-9]
            net = round(restant, 2)
        par_annee[y] = {
            "gain_brut": gain, "gain_net_imposable": net,
            "report_apres": round(sum(v[1] for v in vintages), 2),
        }
        if y == annee:
            net_annee = net

    # Purge finale relative a `annee` (pas seulement a la derniere annee
    # avec transactions) -- si `annee` n'a elle-meme aucun gain/perte, le
    # temps a quand meme pu faire expirer un vintage depuis la derniere
    # annee traitee.
    vintages = [v for v in vintages if annee - v[0] <= 10]
    report = round(sum(v[1] for v in vintages), 2)

    regimes = compare_regimes(autres_revenus, net_annee, parts)
    return {
        "annee": annee,
        "gain_brut": round(gains.get(annee, 0.0), 2),
        "gain_net_imposable": net_annee,
        "report_moins_values_restant": report,
        "historique_par_annee": par_annee,
        **regimes,
    }
