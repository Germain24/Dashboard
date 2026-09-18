"""Matching aliment → produit Super C (superc.ca) + calcul des quantités (paquets)
pour le panier automatique (spec §Phase 2).

Réutilise le matching mots-clés déjà en place pour les prix
(`adonis_pricing._matches` / `adonis_price_per_100g_edible` /
`purchase_unit_weight_kg`)
et le mapping catalogue `CATALOG_MAP` : on retrouve donc **le même produit que
l'optimiseur a chiffré** (le moins cher au 100 g comestible). Pur & testable ;
le remplissage réel du panier est fait par Claude-in-Chrome (runbook dédié).
"""
from __future__ import annotations

import math

from app.services.sante.adonis_pricing import (
    _EDIBLE_DEFAULT,
    _matches,
    adonis_price_per_100g_edible,
    purchase_unit_weight_kg,
)
from app.services.sante.superc_catalog_rebuild import CATALOG_MAP


def _product_id(item: dict) -> str:
    return str(item.get("id") or item.get("sku") or "")


def _same_product(cache_items: list[dict], product_id: str) -> dict | None:
    """Version la moins chère d'un UPC (courant/circulaire)."""
    matches = [it for it in cache_items if _product_id(it) == str(product_id)]
    priced = [it for it in matches if isinstance(it.get("price"), (int, float))]
    return min(priced, key=lambda it: float(it["price"])) if priced else (matches[0] if matches else None)


def best_product(cache_items: list[dict], spec: dict) -> dict | None:
    """Produit Super C le MOINS cher (CAD/100 g comestible) matchant `spec`.

    Si aucun produit matché n'a de prix dérivable, retourne le PREMIER matché
    (pour avoir un id à ajouter au panier, à vérifier). None si aucun match.
    """
    matches = [
        it for it in cache_items
        if (it.get("name") or it.get("href")) and _matches(it, spec)
    ]
    if not matches:
        return None
    edible = spec.get("edible", _EDIBLE_DEFAULT)
    priced = [
        (p, it) for it in matches
        if (p := adonis_price_per_100g_edible(it, edible)) is not None
    ]
    if priced:
        return min(priced, key=lambda x: x[0])[1]
    return matches[0]   # matché mais non chiffrable → à vérifier


def cart_plan(
    shopping_list: list[dict], cache_items: list[dict], item_map: dict | None = None,
    *, product_choices: dict[str, dict] | None = None, shopping_day=None,
) -> list[dict]:
    """Pour chaque item à acheter : `{aliment, product_id, product_name, href,
    format, qty, prix_estime, a_verifier}`.

    `qty = ceil(a_acheter_g / poids_du_format)` (≥ 1) ; format non exploitable ou
    aliment non matché → `qty = 1`, `a_verifier = True`.
    """
    if item_map is None:
        item_map = CATALOG_MAP
    from app.services.cuisine import student_discount
    from app.services.sante.aliments import load_reservoir_product_refs

    reservoir_refs = load_reservoir_product_refs()
    product_choices = product_choices or {}
    discount = student_discount.factor(shopping_day)
    out: list[dict] = []
    for item in shopping_list:
        aliment = item.get("aliment")
        a_acheter = item.get("a_acheter_g")
        besoin_g = float(a_acheter if a_acheter is not None else item.get("quantite_g") or 0.0)
        spec = item_map.get(aliment) if aliment else None
        hinted_id = item.get("product_id") or reservoir_refs.get(str(aliment or ""))
        product = product_choices.get(str(aliment or ""))
        if product is None and hinted_id:
            product = _same_product(cache_items, str(hinted_id))
        if product is None and spec:
            product = best_product(cache_items, spec)

        entry: dict = {
            "aliment": aliment, "product_id": None, "product_name": None,
            "href": None, "format": None, "qty": 1, "prix_estime": None,
            "a_verifier": True,
        }
        if product is not None:
            entry["product_id"] = product.get("id")
            entry["product_name"] = product.get("name")
            entry["href"] = product.get("href")
            entry["format"] = product.get("format")
            package_price = product.get("price")
            if isinstance(package_price, (int, float)):
                entry["prix_estime"] = round(float(package_price) * discount, 2)
            wkg = purchase_unit_weight_kg(product)
            if wkg and wkg > 0:
                entry["qty"] = max(1, math.ceil(besoin_g / (wkg * 1000.0)))
                entry["a_verifier"] = False
            entry["promo"] = bool(product.get("on_sale") or product.get("_flyer"))
        out.append(entry)
    return out


def resolve_products(aliments: list[str], cache_items: list[dict]) -> dict[str, dict]:
    """Résout une seule fois l'aliment vers le produit qui tarifera aussi le panier.

    Les lignes du réservoir utilisent leur UPC exact. Les aliments curés passent
    par leur mapping contrôlé. Un produit sans prix au poids exploitable est
    écarté : il ne doit jamais entrer silencieusement dans l'optimisation.
    """
    from app.services.sante.aliments import load_reservoir_product_refs

    refs = load_reservoir_product_refs()
    out: dict[str, dict] = {}
    for aliment in aliments:
        product = _same_product(cache_items, refs[aliment]) if aliment in refs else None
        if product is None and (spec := CATALOG_MAP.get(aliment)):
            # Entre références équivalentes, le prix au poids prime toujours.
            # Le montant du paquet reste affiché dans le panier, mais ne doit
            # pas faire gagner artificiellement un petit format plus cher/kg.
            matches = [
                item for item in cache_items
                if (item.get("name") or item.get("href"))
                and _matches(item, spec)
                and isinstance(item.get("price"), (int, float))
                and adonis_price_per_100g_edible(
                    item, spec.get("edible", _EDIBLE_DEFAULT)
                ) is not None
                and (
                    purchase_unit_weight_kg(item) is not None
                )
            ]
            edible = spec.get("edible", _EDIBLE_DEFAULT)
            product = min(
                matches,
                key=lambda item: float(adonis_price_per_100g_edible(item, edible)),
            ) if matches else None
        if product is None:
            continue
        spec = CATALOG_MAP.get(aliment, {})
        if adonis_price_per_100g_edible(product, spec.get("edible", _EDIBLE_DEFAULT)) is None:
            continue
        if not isinstance(product.get("price"), (int, float)):
            continue
        if purchase_unit_weight_kg(product) is None:
            continue
        out[aliment] = product
    return out
