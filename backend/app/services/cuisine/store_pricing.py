"""Prix Super C pour la liste de courses hebdo (magasin unique).

Pour chaque item, détermine sa catégorie d'achat (store_categories.py) puis
lit le meilleur prix Super C (prix courant + circulaire). Voir
orchestration/a-faire/2026-07-14-superc-unique-design.md (Phase 1).

Historique : le système comparait autrefois Super C / Adonis / Lufa par
catégorie. Lufa retiré le 2026-07-07 (compte impossible sans commande), puis
passage à Super C unique le 2026-07-14 (décision user : éviter de faire
plusieurs magasins). Adonis n'est plus une source de prix pour les courses ;
la branche `adonis` de `load_cached_items` reste en place mais dormante.

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

# Magasin unique par catégorie : tout Super C (décision user 2026-07-14, cf.
# orchestration/a-faire/2026-07-14-superc-unique-design.md). Fin de la
# comparaison multi-magasins ; Adonis n'est plus une source pour les courses.
CATEGORY_STORES: dict[str, str] = {
    "pantry": "superc",
    "viande_volume": "superc",
    "viande_noble": "superc",
    "tofu_proteines": "superc",
    "fruits_legumes": "superc",
}

_STORE_LABELS = {"superc": "Super C", "adonis": "Adonis"}

_CACHE_FILES = {
    "superc": "superc.json",
    "superc_flyer": "superc_flyer.json",
}

_SCRAPERS = {
    "superc": ".superc_scrape.mjs",
    "superc_flyer": ".superc_flyer_scrape.mjs",
}


def _cache_path(store: str) -> Path:
    return settings.imports_dir / "Cuisine" / _CACHE_FILES[store]


def load_cached_items(store: str) -> list[dict]:
    """Items en cache pour `store` ("superc", "superc_flyer"), ou liste vide
    si absent/illisible. "adonis" réutilise le cache existant d'adonis_pricing.py."""
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
    catégorie est inconnue ou qu'aucun prix n'a pu être matché. Magasin unique :
    tout passe par Super C (promo circulaire incluse via _best_price)."""
    categorie = store_categories.categorie_achat(ingredient)
    if categorie is None or categorie not in CATEGORY_STORES:
        return None
    store = CATEGORY_STORES[categorie]
    result = _best_price(store, ingredient)
    if result is None:
        return None
    price, promo = result
    return {"magasin": _STORE_LABELS[store], "prix_estime": round(price, 2), "promo": promo}


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


def _current_week_search_terms() -> list[str]:
    """Mots-clés de recherche EN pour la semaine courante, dérivés de la liste
    de courses (compute_shopping) via store_categories.search_keywords.

    Best-effort : toute erreur (DB indisponible au démarrage, etc.) retourne
    une liste vide plutôt que de lever — le rafraîchissement au démarrage ne
    doit jamais dépendre d'un état applicatif spécifique."""
    try:
        import datetime as dt

        from sqlmodel import Session

        from app.core.db import engine
        from app.services.cuisine.shopping_list import compute_shopping

        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday())
        with Session(engine) as session:
            items = compute_shopping(session, monday.isoformat())
        terms: list[str] = []
        seen: set[str] = set()
        for item in items:
            for kw in store_categories.search_keywords(item.get("ingredient", "")):
                if kw not in seen:
                    seen.add(kw)
                    terms.append(kw)
        return terms
    except Exception as exc:
        logger.warning("[store_pricing] _current_week_search_terms: %s", exc)
        return []


def refresh_if_stale(store: str, max_age_h: float, terms: list[str] | None = None) -> bool:
    """Relance le scraper `store` si son cache est périmé. True si relancé.

    Best-effort : node/Edge/réseau absents ou scrape en échec -> cache conservé."""
    if _cache_age_seconds(store) < max_age_h * 3600:
        return False
    repo_root = settings.data_dir.parent
    script = repo_root / "frontend" / _SCRAPERS[store]
    if not script.exists():
        return False
    cmd = ["node", script.name, str(_cache_path(store))]
    if terms:
        cmd.extend(terms)
    try:
        subprocess.run(
            cmd,
            cwd=str(script.parent),
            timeout=float(os.getenv("STORE_SCRAPE_TIMEOUT_SEC", "150")),
            capture_output=True,
        )
        return True
    except Exception as exc:
        logger.warning("[store_pricing] scrape %s échoué (%s) — prix en cache conservés", store, exc)
        return False


def refresh_all_if_stale(max_age_h: float = 12.0) -> None:
    """Rafraîchit les caches magasin (superc/superc_flyer) si périmés.

    Appelé en tâche de fond au démarrage du backend (Task 4) — jamais
    bloquant, jamais fatal. Désactivable via STORE_PRICING_REFRESH=0."""
    if os.getenv("STORE_PRICING_REFRESH", "1") not in ("1", "true", "True"):
        return
    terms = _current_week_search_terms()
    for store in _SCRAPERS:
        try:
            refresh_if_stale(store, max_age_h, terms=terms if store != "superc_flyer" else None)
        except Exception as exc:
            logger.warning("[store_pricing] refresh_all_if_stale(%s): %s", store, exc)
