"""Conversions sûres du garde-manger et valorisation du stock en fenêtre.

Le stock périssable est consommé en priorité (coût imputé 0 %), le stock
durable garde une valeur de remplacement de 50 %, et les quantités au-delà du
stock disponible reviennent au coût normal. Le coût payé en caisse reste
distinct du coût imputé au plan.
"""
from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any, Mapping

_UNIT_G = {"g": 1.0, "kg": 1000.0, "mg": 0.001, "ml": 1.0, "l": 1000.0}
_COUNT_UNITS_AS_GRAMS = {
    "comprime", "comprimes", "tablette", "tablettes",
    "tablet", "tablets", "capsule", "capsules",
}
_PERISHABLE_FACTOR = 0.0
_DURABLE_FACTOR = 0.5
_WARNING_DAYS = 3


def _norm(value: Any) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", str(value or "").lower())
        if not unicodedata.combining(char)
    ).strip()


def _valid_grams(item: Mapping[str, Any]) -> float:
    """Convert mass directly and liquids approximately at 1 ml ≈ 1 g.

    Olive oil uses a typical density approximation (0.92 g/ml); honey/syrup
    uses 1.35 g/ml. Other liquids default to water density as requested.
    """
    try:
        quantity = float(item.get("quantite") or 0)
    except (TypeError, ValueError):
        return 0.0
    unit = _norm(item.get("unite") or "g")
    if unit in _COUNT_UNITS_AS_GRAMS:
        # Coarse inventory-only estimate: one rounded tablet/capsule ≈ 1 g.
        # Supplement entries remain excluded from food optimization below.
        return float(max(0, round(quantity)))
    factor = _UNIT_G.get(unit)
    if unit in {"ml", "l"}:
        name = _norm(item.get("catalog_food") or item.get("ingredient"))
        if any(marker in name for marker in ("huile", "oil")):
            factor *= 0.92
        elif any(marker in name for marker in ("miel", "sirop", "honey", "syrup")):
            factor *= 1.35
    if factor is None or quantity <= 0:
        # Tablets and unknown units need an explicit serving-size conversion.
        return 0.0
    return quantity * factor


def _expiry_state(date_peremption: Any, today: date) -> str:
    if not date_peremption:
        return "no_date"
    try:
        expiry = date.fromisoformat(str(date_peremption))
    except ValueError:
        return "invalid"
    days_left = (expiry - today).days
    if days_left < 0:
        return "expired"
    if days_left <= _WARNING_DAYS:
        return "warning"
    return "ok"


def _is_perishable(item: Mapping[str, Any]) -> bool:
    if item.get("perissable") is True or item.get("perishable") is True:
        return True
    rayon = _norm(item.get("rayon"))
    if any(marker in rayon for marker in (
        "fruit", "legume", "produit laitier", "viande", "poisson",
        "boulangerie", "frais", "traiteur frais",
    )):
        return True
    product = _norm(item.get("catalog_food") or item.get("ingredient"))
    return any(marker in product for marker in (
        "tomate fraiche", "tomates fraiches", "salade fraiche",
        "legumes frais", "fruits frais",
    ))


def _is_shelf_stable(item: Mapping[str, Any]) -> bool:
    rayon = _norm(item.get("rayon"))
    return any(marker in rayon for marker in ("epicerie seche", "conserves", "surgeles"))


def pantry_cost_factor(item: Mapping[str, Any], today: date | None = None) -> float | None:
    """Return 0 for perishable/near-expiry stock, .5 for durable, None if unusable."""
    if "complement" in _norm(item.get("rayon")):
        return None
    ref = today or date.today()
    expiry = _expiry_state(item.get("date_peremption"), ref)
    shelf_stable = _is_shelf_stable(item)
    if expiry == "expired" and not shelf_stable:
        return None
    kind = _norm(item.get("type_aliment"))
    if kind in {
        "supplement", "supplements", "supplement alimentaire",
        "non mappe", "non_mappe", "non-alimente", "non alimentaire",
    }:
        return None
    if expiry == "warning" and not shelf_stable:
        return _PERISHABLE_FACTOR
    return _PERISHABLE_FACTOR if _is_perishable(item) else _DURABLE_FACTOR


def load_pantry_stock(
    items: list[dict], *, today: date | None = None
) -> dict[str, list[dict[str, float]]]:
    """Items utilisables → lots de stock par aliment, sans perdre péremptions.

    Chaque lot contient ``available_g`` et ``cost_factor``. Les doublons restent
    séparés afin que plusieurs dates ou catégories du même aliment soient
    valorisées dans l'ordre le plus périssable en premier.
    """
    out: dict[str, list[dict[str, float]]] = {}
    for item in items:
        name = str(item.get("catalog_food") or item.get("ingredient") or "").strip()
        grams = _valid_grams(item)
        factor = pantry_cost_factor(item, today)
        if not name or grams <= 0 or factor is None:
            continue
        out.setdefault(name, []).append({"available_g": grams, "cost_factor": factor})
    for lots in out.values():
        lots.sort(key=lambda lot: lot["cost_factor"])
    return out


def pantry_stock_grams(stock: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, float]:
    """Collapse usable lots to gram totals for shopping-list deductions/shortlist."""
    return {
        name: sum(max(0.0, float(lot.get("available_g") or 0.0)) for lot in lots)
        for name, lots in stock.items()
    }


def load_pantry_grams(items: list[dict], *, today: date | None = None) -> dict[str, float]:
    """Items garde-manger → grammes utilisables; périmés et unités ambiguës exclus."""
    return pantry_stock_grams(load_pantry_stock(items, today=today))


def normalize_stock_lots(value: Any) -> list[tuple[float, float]]:
    """Normalize one optimizer food's lot profile to ``(units_100g, factor)``."""
    if isinstance(value, Mapping):
        lots = [value]
    elif isinstance(value, (list, tuple)):
        lots = value
    else:
        return []
    result: list[tuple[float, float]] = []
    for lot in lots:
        if not isinstance(lot, Mapping):
            continue
        try:
            grams = float(lot.get("available_g") or 0.0)
            factor = float(lot.get("cost_factor", _DURABLE_FACTOR))
        except (TypeError, ValueError):
            continue
        if grams <= 0:
            continue
        result.append((grams / 100.0, min(1.0, max(0.0, factor))))
    return sorted(result, key=lambda pair: pair[1])


def _used_stock_cost(
    quantity_g: float,
    unit_price_per_100g: float,
    lots: list[tuple[float, float]],
) -> float:
    """Replacement value of the portion consumed from existing stock."""
    remaining = max(0.0, float(quantity_g)) / 100.0
    cost = 0.0
    price = max(0.0, float(unit_price_per_100g))
    for units, factor in lots:
        used = min(remaining, units)
        cost += used * price * factor
        remaining -= used
        if remaining <= 1e-12:
            break
    return cost


def apply_pantry_deduction(
    shopping_list: list[dict], pantry_g: dict[str, float]
) -> tuple[list[dict], float]:
    """Déduit uniquement le stock utilisable de la liste et chiffre le déficit."""
    out: list[dict] = []
    cout_a_payer = 0.0
    for item in shopping_list:
        besoin = float(item.get("quantite_g") or 0.0)
        stock = float(pantry_g.get(item.get("aliment", ""), 0.0))
        dispo = min(besoin, stock)
        a_acheter = besoin - dispo
        if a_acheter <= 1e-9:
            continue
        prix_total = float(item.get("prix") or 0.0)
        prix_achat = round(prix_total * (a_acheter / besoin), 2) if besoin > 0 else prix_total
        new = dict(item)
        new["dispo_g"] = round(dispo, 1)
        new["a_acheter_g"] = round(a_acheter, 1)
        new["prix"] = prix_achat
        cout_a_payer += prix_achat
        out.append(new)
    return out, round(cout_a_payer, 2)
