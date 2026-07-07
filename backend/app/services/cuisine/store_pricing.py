"""Comparaison de prix Super C / Adonis / Lufa pour la liste de courses hebdo.

Pour chaque item, détermine sa catégorie d'achat (store_categories.py) puis
compare le prix entre les 2 magasins pertinents pour cette catégorie (le 3e
est exclu, "éviter" dans la spec). Voir
orchestration/a-faire/2026-07-06-lufa-superc-comparaison-prix-design.md.

Best-effort partout : un cache manquant, un item non catégorisé, ou une
erreur inattendue ne casse jamais la liste de courses — l'item reste juste
sans annotation magasin. Le rafraîchissement (scrape navigateur) suit le
même contrat que adonis_pricing.py : jamais bloquant, jamais fatal.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path

from app.core.config import settings
from app.services.cuisine import store_categories

logger = logging.getLogger(__name__)

# {categorie: (magasin_a, magasin_b)} — le 3e magasin de la table de priorité
# (design doc) est exclu ("éviter") pour cette catégorie.
CATEGORY_STORES: dict[str, tuple[str, str]] = {
    "pantry": ("superc", "adonis"),
    "viande_volume": ("adonis", "superc"),
    "viande_noble": ("lufa", "adonis"),
    "tofu_proteines": ("adonis", "superc"),
    "fruits_legumes": ("adonis", "lufa"),
}

# Exception Fruits/Légumes : ces aliments restent toujours Super C, jamais
# comparés (produits de base bon marché, cf. tableau du user).
FRUITS_LEGUMES_SUPERC_ONLY = {"Patate douce", "Oignon"}

_STORE_LABELS = {"superc": "Super C", "adonis": "Adonis", "lufa": "Lufa"}

_CACHE_FILES = {
    "superc": "superc.json",
    "superc_flyer": "superc_flyer.json",
    "lufa": "lufa.json",
}

_SCRAPERS = {
    "superc": ".superc_scrape.mjs",
    "superc_flyer": ".superc_flyer_scrape.mjs",
    "lufa": ".lufa_scrape.mjs",
}


def _cache_path(store: str) -> Path:
    return settings.imports_dir / "Cuisine" / _CACHE_FILES[store]


def load_cached_items(store: str) -> list[dict]:
    """Items en cache pour `store` ("superc", "superc_flyer", "lufa"), ou
    liste vide si absent/illisible. "adonis" réutilise le cache existant
    d'adonis_pricing.py."""
    if store == "adonis":
        from app.services.sante.adonis_pricing import load_cached_items as _adonis_load
        return _adonis_load()
    path = _cache_path(store)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def _keyword_match(item: dict, ingredient: str) -> bool:
    n = (str(item.get("name") or "") + " " + str(item.get("href") or "")).lower()
    return any(re.search(r"\b" + re.escape(kw), n) for kw in store_categories.search_keywords(ingredient))


def _cheapest(items: list[dict], ingredient: str) -> dict | None:
    matches = [it for it in items if it.get("price") and _keyword_match(it, ingredient)]
    if not matches:
        return None
    return min(matches, key=lambda it: it["price"])


def _best_price(store: str, ingredient: str) -> tuple[float, bool] | None:
    """(prix, promo) le moins cher pour `ingredient` chez `store`. Pour
    Super C, compare aussi la circulaire (superc_flyer) : un rabais circulaire
    moins cher que le prix courant gagne et est marqué promo=True."""
    regular = _cheapest(load_cached_items(store), ingredient)
    if store == "superc":
        flyer = _cheapest(load_cached_items("superc_flyer"), ingredient)
        if flyer and (regular is None or flyer["price"] < regular["price"]):
            return flyer["price"], True
    if regular is None:
        return None
    return regular["price"], bool(regular.get("on_sale"))


def recommend_store(ingredient: str) -> dict | None:
    """{"magasin": str, "prix_estime": float, "promo": bool}, ou None si la
    catégorie est inconnue ou qu'aucun prix n'a pu être matché."""
    if ingredient in FRUITS_LEGUMES_SUPERC_ONLY:
        result = _best_price("superc", ingredient)
        if result is None:
            return None
        return {"magasin": "Super C", "prix_estime": round(result[0], 2), "promo": result[1]}

    categorie = store_categories.categorie_achat(ingredient)
    if categorie is None or categorie not in CATEGORY_STORES:
        return None
    store_a, store_b = CATEGORY_STORES[categorie]
    result_a = _best_price(store_a, ingredient)
    result_b = _best_price(store_b, ingredient)
    if result_a is None and result_b is None:
        return None
    if result_b is None or (result_a is not None and result_a[0] <= result_b[0]):
        winner, (price, promo) = store_a, result_a
    else:
        winner, (price, promo) = store_b, result_b
    return {"magasin": _STORE_LABELS[winner], "prix_estime": round(price, 2), "promo": promo}


def apply_recommendations(items: list[dict]) -> list[dict]:
    """Retourne une copie de `items` annotée avec magasin_recommande /
    prix_estime / promo quand une recommandation existe. Best-effort : une
    erreur sur un item est loggée et ignorée, jamais propagée."""
    out = []
    for item in items:
        new_item = dict(item)
        try:
            rec = recommend_store(item["ingredient"])
        except Exception as exc:
            logger.warning("[store_pricing] recommandation ignorée pour %s (%s)", item.get("ingredient"), exc)
            rec = None
        if rec:
            new_item["magasin_recommande"] = rec["magasin"]
            new_item["prix_estime"] = rec["prix_estime"]
            new_item["promo"] = rec["promo"]
        out.append(new_item)
    return out


# ── Rafraîchissement (best-effort, jamais bloquant) ───────────────────────────

def _cache_age_seconds(store: str) -> float:
    try:
        return time.time() - _cache_path(store).stat().st_mtime
    except OSError:
        return float("inf")


def refresh_if_stale(store: str, max_age_h: float) -> bool:
    """Relance le scraper `store` si son cache est périmé. True si relancé.

    Best-effort : node/Edge/réseau absents ou scrape en échec -> cache conservé."""
    if _cache_age_seconds(store) < max_age_h * 3600:
        return False
    repo_root = settings.data_dir.parent
    script = repo_root / "frontend" / _SCRAPERS[store]
    if not script.exists():
        return False
    try:
        subprocess.run(
            ["node", script.name, str(_cache_path(store))],
            cwd=str(script.parent),
            timeout=float(os.getenv("STORE_SCRAPE_TIMEOUT_SEC", "150")),
            capture_output=True,
        )
        return True
    except Exception as exc:
        logger.warning("[store_pricing] scrape %s échoué (%s) — prix en cache conservés", store, exc)
        return False


def refresh_all_if_stale(max_age_h: float = 12.0) -> None:
    """Rafraîchit les 3 caches magasin (superc/superc_flyer/lufa) si périmés.

    Appelé en tâche de fond au démarrage du backend (Task 4) — jamais
    bloquant, jamais fatal. Désactivable via STORE_PRICING_REFRESH=0."""
    if os.getenv("STORE_PRICING_REFRESH", "1") not in ("1", "true", "True"):
        return
    for store in _SCRAPERS:
        try:
            refresh_if_stale(store, max_age_h)
        except Exception as exc:
            logger.warning("[store_pricing] refresh_all_if_stale(%s): %s", store, exc)
