"""Prix Super C pour la liste de courses hebdo (magasin unique).

Pour chaque item, détermine sa catégorie d'achat (store_categories.py) puis
lit le meilleur prix Super C (prix courant + circulaire). Voir
orchestration/a-faire/2026-07-14-superc-unique-design.md (Phase 1).

Historique : le système comparait autrefois Super C / Adonis / Lufa par
catégorie. Lufa retiré le 2026-07-07 (compte impossible sans commande), puis
passage à Super C unique le 2026-07-14 (décision user : éviter de faire
plusieurs magasins). Adonis retiré définitivement le 2026-07-17 (décision
user : plus aucune source de prix que Super C, courses et optimiseur).

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
import sys
import threading
import time
from pathlib import Path

from app.core.config import settings
from app.services.cuisine import store_categories

logger = logging.getLogger(__name__)
_refresh_lock = threading.Lock()

# Magasin unique par catégorie : tout Super C (décision user 2026-07-14, cf.
# orchestration/a-faire/2026-07-14-superc-unique-design.md). Fin de la
# comparaison multi-magasins ; Adonis n'est plus une source pour les courses.
CATEGORY_STORES: dict[str, str] = {
    "pantry": "superc",
    "viande_volume": "superc",
    "viande_noble": "superc",
    "tofu_proteines": "superc",
    "laitiers": "superc",
    "fruits_legumes": "superc",
}

_STORE_LABELS = {"superc": "Super C", "adonis": "Adonis"}

_CACHE_FILES = {
    "superc": "superc.json",
    "superc_flyer": "superc_flyer.json",
}

_SCRAPERS = {
    "superc": ".superc_scrape.mjs",
    "superc_flyer": ".superc_scrape.mjs",
}


def _cache_path(store: str) -> Path:
    return settings.imports_dir / "Cuisine" / _CACHE_FILES[store]


def load_cached_items(store: str) -> list[dict]:
    """Items en cache pour `store` ("superc", "superc_flyer"), ou liste vide
    si absent/illisible."""
    path = _cache_path(store)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def load_superc_pricing_items() -> list[dict]:
    """Catalogue courant + circulaire, avec provenance conservée."""
    regular = [dict(item, _flyer=False) for item in load_cached_items("superc")]
    by_id = {
        str(item.get("id") or item.get("sku")): item
        for item in regular if item.get("id") or item.get("sku")
    }
    flyer = []
    for raw in load_cached_items("superc_flyer"):
        product_id = str(raw.get("id") or raw.get("sku") or "")
        base = by_id.get(product_id, {})
        # La circulaire contient parfois seulement le nom et le prix. On garde
        # le format/lien du catalogue courant pour que le panier reste achetable.
        values = {key: value for key, value in raw.items() if value not in (None, "")}
        flyer.append({**base, **values, "_flyer": True})
    return [*regular, *flyer]


def _keyword_match(item: dict, ingredient: str) -> bool:
    # Nom SEUL (pas `href`) : sur superc.ca, href est un fil d'Ariane de
    # CATÉGORIES (ex. tout produit laitier a "oeufs" dans son href via le
    # rayon "produits-laitiers-et-oeufs") -> le matcher ferait fuiter le rayon
    # entier sur chaque produit. Même fix que adonis_pricing._matches, cf.
    # commentaire là-bas (Task 3, repoint superc.ca 2026-07-23).
    n = str(item.get("name") or "").lower()
    return any(re.search(r"\b" + re.escape(kw), n) for kw in store_categories.search_keywords(ingredient))


def _cheapest(items: list[dict], ingredient: str) -> dict | None:
    matches = [it for it in items
               if it.get("price")
               and store_categories.est_alimentaire(it)
               and _keyword_match(it, ingredient)]
    if not matches:
        return None
    return min(matches, key=lambda it: it["price"])


def _best_price(store: str, ingredient: str) -> tuple[float, bool] | None:
    """(prix, promo) le moins cher pour `ingredient` chez `store`. Pour
    Super C, compare aussi la circulaire (superc_flyer) : un rabais circulaire
    moins cher que le prix courant gagne et est marqué promo=True.

    Prix AVANT rabais étudiant : la comparaison courant/circulaire doit se faire
    à taux égal, et le rabais s'applique de toute façon aux deux (cf.
    `student_discount`). Il est appliqué une seule fois, dans `recommend_store`.
    """
    regular = _cheapest(load_cached_items(store), ingredient)
    if store == "superc":
        flyer = _cheapest(load_cached_items("superc_flyer"), ingredient)
        if flyer and (regular is None or flyer["price"] < regular["price"]):
            return flyer["price"], True
    if regular is None:
        return None
    return regular["price"], bool(regular.get("on_sale"))


def recommend_store(ingredient: str, shopping_day=None) -> dict | None:
    """{"magasin": str, "prix_estime": float, "promo": bool}, ou None si la
    catégorie est inconnue ou qu'aucun prix n'a pu être matché. Magasin unique :
    tout passe par Super C (promo circulaire incluse via _best_price).

    `shopping_day` : jour de paiement du panier. Lundi→mercredi, le rabais
    étudiant de 10 % est appliqué au prix estimé (promotions comprises)."""
    from app.services.cuisine import student_discount

    categorie = store_categories.categorie_achat(ingredient)
    if categorie is None or categorie not in CATEGORY_STORES:
        return None
    store = CATEGORY_STORES[categorie]
    result = _best_price(store, ingredient)
    if result is None:
        return None
    price, promo = result
    price = student_discount.apply(price, shopping_day)
    return {"magasin": _STORE_LABELS[store], "prix_estime": round(price, 2), "promo": promo}


def apply_recommendations(items: list[dict], shopping_day=None) -> list[dict]:
    """Retourne une copie de `items` annotée avec magasin_recommande /
    prix_estime / promo quand une recommandation existe. Best-effort : une
    erreur sur un item est loggée et ignorée, jamais propagée."""
    out = []
    for item in items:
        new_item = dict(item)
        try:
            rec = recommend_store(item["ingredient"], shopping_day)
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
        path = _cache_path(store)
        # Un fichier partiel contient déjà tous les prix réussis, mais ne doit
        # pas être déclaré « frais » : le prochain lancement doit reprendre les
        # termes restants grâce à completed_terms.
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Les anciens fichiers sans marqueur étaient parfois de minuscules
        # captures partielles (42 produits dans le cas observé) mais étaient
        # tout de même considérés frais pendant 12 h. Le catalogue courant
        # n'est frais que si le scraper moderne a explicitement terminé.
        if store.startswith("superc") and payload.get("refresh_complete") is not True:
            return float("inf")
        if store.startswith("superc") and str(payload.get("store_id") or "") != "572":
            return float("inf")
        return time.time() - path.stat().st_mtime
    except (OSError, ValueError, TypeError):
        return float("inf")


def _catalog_search_terms() -> list[str]:
    """Mots-clés de recherche pour TOUT le catalogue d'aliments.

    C'est le catalogue — pas la liste de courses — qui alimente l'optimiseur :
    ce sont donc ses prix qui doivent être frais. Les dériver des courses de la
    semaine avait un défaut fatal : sans plan de repas généré, la liste est
    vide, le scraper était lancé sans aucun terme et ne rafraîchissait rien. Les
    prix restaient figés (14 jours constatés) alors qu'une optimisation tournait
    dessus.

    Best-effort : toute erreur retourne une liste vide plutôt que de lever — le
    rafraîchissement au démarrage ne doit jamais dépendre d'un état applicatif.
    """
    try:
        from app.services.sante.aliments import load_aliments_dataframe
        from app.services.sante.fenetre_service import (
            OPTIMIZER_PRIORITY_FOOD_ORDER,
            OPTIMIZER_PRIORITY_FOODS,
        )

        terms: list[str] = []
        seen: set[str] = set()
        names = [str(name) for name in load_aliments_dataframe().index]
        priority = [name for name in OPTIMIZER_PRIORITY_FOOD_ORDER if name in names]
        priority.extend(
            name for name in names
            if name in OPTIMIZER_PRIORITY_FOODS and name not in priority
        )
        others = [name for name in names if name not in OPTIMIZER_PRIORITY_FOODS]

        def add(term: str) -> None:
            if term not in seen:
                seen.add(term)
                terms.append(term)

        # Premier mot-clé de CHAQUE aliment essentiel avant ses synonymes : si
        # Cloudflare coupe la collecte, on aura couvert le plus de familles
        # possibles plutôt que dix variantes des premiers aliments seulement.
        for name in priority:
            keywords = store_categories.search_keywords(name)
            if keywords:
                add(keywords[0])
        for name in priority:
            for kw in store_categories.search_keywords(name)[1:]:
                add(kw)
        for name in others:
            for kw in store_categories.search_keywords(name):
                add(kw)
        return terms
    except Exception as exc:
        logger.warning("[store_pricing] _catalog_search_terms: %s", exc)
        return []


#: Conservé sous son ancien nom : d'autres appels/tests peuvent s'y référer.
_current_week_search_terms = _catalog_search_terms


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
    if store == "superc":
        # Une navigation par rayon couvre tout le magasin et évite les
        # centaines de requêtes /recherche qui déclenchaient Cloudflare.
        cmd.append("--rayons")
    elif store == "superc_flyer":
        cmd.append("--circulaire")
    elif terms:
        cmd.extend(terms)
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(script.parent),
            # Couvrir tout le catalogue demande 178 recherches, soit 1441 s
            # mesurés de bout en bout (mise en route Cloudflare + sélection du
            # magasin comprises). Le plafond de 150 s coupait systématiquement le
            # scrape avant la fin, en laissant le cache inchangé et sans qu'aucune
            # erreur ne remonte — les prix sont ainsi restés figés 14 jours.
            # Le rythme anti-débit volontaire (pause après chaque paire de
            # pages) peut faire durer un catalogue complet plusieurs heures.
            timeout=float(os.getenv("STORE_SCRAPE_TIMEOUT_SEC", "21600")),
            capture_output=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode(errors="replace") if completed.stderr else ""
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else "aucun détail"
            logger.warning(
                "[store_pricing] scrape %s interrompu (code %s : %s); "
                "résultats partiels sauvegardés et repris au prochain lancement",
                store, completed.returncode, detail,
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.warning(
            "[store_pricing] scrape %s interrompu par le délai; résultats partiels "
            "sauvegardés et repris au prochain lancement",
            store,
        )
        return False
    except Exception as exc:
        logger.warning("[store_pricing] scrape %s échoué (%s) — prix en cache conservés", store, exc)
        return False


def _rebuild_superc_reservoir(repo_root: Path) -> bool:
    """Relie le nouveau catalogue Atwater à CIQUAL après un crawl complet."""
    script = repo_root / "backend" / "scripts" / "build_reservoir.py"
    if not script.exists():
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(script.parent.parent),
            timeout=float(os.getenv("SUPERC_RESERVOIR_TIMEOUT_SEC", "600")),
            capture_output=True,
        )
        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace").strip().splitlines()
            logger.warning("[store_pricing] reconstruction CIQUAL échouée: %s", detail[-1] if detail else result.returncode)
            return False
        logger.info("[store_pricing] réservoir Super C/CIQUAL reconstruit")
        return True
    except Exception as exc:
        logger.warning("[store_pricing] reconstruction CIQUAL ignorée (%s)", exc)
        return False


def refresh_all_if_stale(max_age_h: float = 12.0) -> None:
    """Rafraîchit les caches magasin (superc/superc_flyer) si périmés.

    Appelé en tâche de fond au démarrage du backend (Task 4) — jamais
    bloquant, jamais fatal. Désactivable via STORE_PRICING_REFRESH=0."""
    if os.getenv("STORE_PRICING_REFRESH", "1") not in ("1", "true", "True"):
        return
    # Le rafraîchissement de démarrage et une génération lancée juste après
    # pouvaient démarrer deux Chrome sur le même cache. Le verrou couvre la
    # vérification d'âge ET le scrape afin que le second appel réutilise le
    # résultat du premier au lieu de déclencher un doublon.
    with _refresh_lock:
        refreshed = False
        for store in _SCRAPERS:
            try:
                refreshed = refresh_if_stale(
                    store, max_age_h,
                    terms=None,
                ) or refreshed
            except Exception as exc:
                logger.warning("[store_pricing] refresh_all_if_stale(%s): %s", store, exc)
        # Après les DEUX collectes : le réservoir inclut ainsi également la
        # nouvelle circulaire, et chaque produit fiable est relié à CIQUAL.
        if refreshed:
            _rebuild_superc_reservoir(settings.data_dir.parent)


def ensure_fresh_prices(max_age_h: float = 12.0) -> None:
    """Garantit des caches vérifiés avant une optimisation.

    Contrairement au rafraîchissement de confort au démarrage, cette fonction
    échoue explicitement si le prix courant ou la circulaire reste périmé. Un
    plan ne peut donc plus être présenté comme chiffré avec des prix frais alors
    que le scrape a été bloqué ou interrompu.
    """
    if os.getenv("STORE_PRICING_REFRESH", "1") not in ("1", "true", "True"):
        return
    refresh_all_if_stale(max_age_h=max_age_h)
    stale = [store for store in _SCRAPERS if _cache_age_seconds(store) >= max_age_h * 3600]
    if stale:
        labels = ", ".join(stale)
        raise RuntimeError(
            f"Prix Super C non vérifiés ({labels}). Termine la vérification de sécurité "
            "ou réessaie le rafraîchissement avant de générer le plan."
        )
