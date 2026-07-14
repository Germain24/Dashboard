"""Phase 3 « Super C unique » — outillage NON destructif de reconstruction des
prix d'`aliments.csv` sur les prix Super C.

Le catalogue est hand-curé (teneurs CIQUAL 2020 + prix Costco relevés à la main,
ajustés à la portion comestible). On ne l'écrase JAMAIS automatiquement :
`scripts/rebuild_superc_catalog.py` lit le cache `superc.json`, calcule les
nouveaux prix pour les aliments matchés, et écrit un CSV **candidat** + un
rapport des aliments **retirés** (aucun match Super C = non vendu → retiré,
décision user 2026-07-14). L'utilisateur revoit puis bascule lui-même.

Ce module ne contient que la logique pure (mapping, plan de reconstruction,
réécriture texte du CSV transposé) ; les I/O vivent dans le script.

Réf : orchestration/a-faire/2026-07-14-superc-unique-design.md (Phase 3).
"""
from __future__ import annotations

from app.services.cuisine.store_categories import NON_PRODUCE_KW
from app.services.sante.adonis_pricing import PRODUCE_MAP, build_price_overlay

# Suppléments / marques que Super C ne vend pas : jamais mappés → toujours
# « non matchés » → retirés du catalogue (décision user). Repérés au suffixe.
_SUPPLEMENT_MARKERS = ("(inshape)", "(on)", "(costco)")


def _is_supplement(name: str) -> bool:
    n = name.lower()
    return any(m in n for m in _SUPPLEMENT_MARKERS)


# Œufs & produits laitiers absents des maps « courses » (seed extensible, même
# philosophie que PRODUCE_MAP : à corriger/étendre au vu des résultats réels).
# `edible` = 1.0 (pas de partie jetée) sauf indication ; `not` exclut les faux
# positifs (Beurre ≠ beurre d'arachide/amande).
_DAIRY_EGGS_SPEC: dict[str, dict] = {
    "Oeufs": {"kw": ["egg"], "edible": 1.0},
    "Fromage cheddar": {"kw": ["cheddar"], "edible": 1.0},
    "Mozzarella": {"kw": ["mozzarella"], "edible": 1.0},
    "Parmesan": {"kw": ["parmesan"], "edible": 1.0},
    "Yogourt grec nature 0%": {"kw": ["greek"], "edible": 1.0},
    "Lait 2%": {"kw": ["milk"], "not": ["almond", "oat", "soy", "coconut"], "edible": 1.0},
    "Lait d'amande non sucre": {"kw": ["almond"], "edible": 1.0},
    "Beurre": {"kw": ["butter"], "not": ["peanut", "almond", "cashew"], "edible": 1.0},
    "Feta": {"kw": ["feta"], "edible": 1.0},
    "Brie": {"kw": ["brie"], "edible": 1.0},
    "Gouda": {"kw": ["gouda"], "edible": 1.0},
    "Gruyere": {"kw": ["gruyere", "gruyère"], "edible": 1.0},
    "Emmental": {"kw": ["emmental"], "edible": 1.0},
    "Fromage de chevre": {"kw": ["goat"], "edible": 1.0},
    "Camembert": {"kw": ["camembert"], "edible": 1.0},
    "Provolone": {"kw": ["provolone"], "edible": 1.0},
    "Lait entier": {"kw": ["whole milk"], "edible": 1.0},
    "Lait ecreme": {"kw": ["skim milk"], "edible": 1.0},
    "Boisson d'avoine": {"kw": ["oat"], "edible": 1.0},
    "Kefir": {"kw": ["kefir"], "edible": 1.0},
    "Fromage blanc": {"kw": ["quark", "fromage blanc"], "edible": 1.0},
}


def _build_catalog_map() -> dict[str, dict]:
    """Mapping aliment FR → {kw, edible, not?} pour TOUT le catalogue.

    Réutilise les mots-clés « courses » (NON_PRODUCE_KW, source unique) + un seed
    œufs/laitiers, avec `edible=1.0` par défaut. Les fruits & légumes (PRODUCE_MAP)
    apportent leur propre fraction comestible et écrasent les doublons éventuels.
    Les suppléments/marques Costco sont EXCLUS (→ retirés à la reconstruction).
    """
    m: dict[str, dict] = {}
    for name, kw in NON_PRODUCE_KW.items():
        if _is_supplement(name):
            continue
        m[name] = {"kw": kw, "edible": 1.0}
    m.update(_DAIRY_EGGS_SPEC)
    m.update(PRODUCE_MAP)   # produce : edible/`not` spécifiques, prioritaires
    return m


CATALOG_MAP: dict[str, dict] = _build_catalog_map()


def catalog_price_overlay(cache_items: list[dict]) -> dict[str, float]:
    """{aliment FR: prix CAD/100 g comestible} pour tout le catalogue, depuis les
    items Super C en cache (schéma Instacart)."""
    return build_price_overlay(cache_items, CATALOG_MAP)


def plan_rebuild(
    catalog_items: list[str], overlay: dict[str, float]
) -> tuple[dict[str, float], list[str]]:
    """Sépare les aliments du catalogue en (matchés → nouveau prix, non matchés).

    Un aliment sans prix Super C matché est « non vendu » → à retirer. L'ordre
    des non matchés suit l'ordre du catalogue (rapport déterministe).
    """
    matched = {name: overlay[name] for name in catalog_items if name in overlay}
    unmatched = [name for name in catalog_items if name not in overlay]
    return matched, unmatched


def _fmt_price(price: float) -> str:
    """Prix en texte pour le CSV (décimales conservées, jamais de notation sci)."""
    return f"{price:.3f}".rstrip("0").rstrip(".")


def rewrite_catalog_csv(
    lines: list[str], matched: dict[str, float], unmatched: list[str]
) -> list[str]:
    """Réécrit le CSV transposé (`;`) en NE touchant QUE la ligne `Prix` (aliments
    matchés) et en RETIRANT les colonnes des aliments non matchés.

    `lines` : lignes du CSV d'origine (sans `\\n` final). Ligne 0 = en-tête
    (`Nutriments;aliment1;aliment2;…`). Toutes les autres teneurs (CIQUAL) sont
    préservées à l'identique. Retourne les nouvelles lignes.
    """
    if not lines:
        return []
    header = lines[0].split(";")
    foods = header[1:]
    unmatched_set = set(unmatched)
    # Indices de colonnes à RETIRER (décalés de 1 : la colonne 0 est le libellé).
    drop = {i + 1 for i, f in enumerate(foods) if f in unmatched_set}
    keep = [i for i in range(len(header)) if i not in drop]

    out: list[str] = []
    for line in lines:
        cells = line.split(";")
        # Pad défensif si une ligne est plus courte que l'en-tête.
        if len(cells) < len(header):
            cells = cells + [""] * (len(header) - len(cells))
        if cells and cells[0] == "Prix":
            for i, f in enumerate(foods):
                if f in matched:
                    cells[i + 1] = _fmt_price(matched[f])
        out.append(";".join(cells[i] for i in keep))
    return out
