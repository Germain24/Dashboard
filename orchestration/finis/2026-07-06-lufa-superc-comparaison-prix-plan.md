# Comparaison de prix Super C / Adonis / Lufa — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Annoter chaque item de la liste de courses hebdo (`/shopping-list/preview`) avec un magasin recommandé (Super C / Adonis / Lufa) et un prix estimé, selon une règle de comparaison par catégorie d'aliment.

**Architecture:** 3 scrapers Playwright (pattern `.adonis_scrape.mjs` existant) écrivent des caches JSON dans `data/imports/Cuisine/`. Un nouveau service pur `store_pricing.py` catégorise chaque ingrédient (`store_categories.py`), compare le prix entre les 2 magasins pertinents pour sa catégorie (le 3e est exclu), et annote les items. `compute_shopping()` applique cette annotation en best-effort. Le rafraîchissement des caches est déclenché en tâche de fond au démarrage du backend, jamais bloquant.

**Tech Stack:** Python (FastAPI, SQLModel), pytest, Node.js + Playwright (`playwright-core` + Edge), Next.js/React (TypeScript).

## Global Constraints

- Best-effort partout : un cache absent, un scraper en échec, ou un item non catégorisé ne doit **jamais** faire échouer `/shopping-list/preview`. Voir le précédent établi par `adonis_pricing.py`.
- Aucune modification de `aliments.csv` ni de l'optimiseur nutrition (`backend/app/services/sante/plan.py`) — hors scope, voir spec.
- Le catalogue produce existant (`PRODUCE_MAP` dans `adonis_pricing.py`) est réutilisé tel quel pour la catégorie `fruits_legumes`, pas dupliqué.
- Spec source : `orchestration/a-faire/2026-07-06-lufa-superc-comparaison-prix-design.md`.

---

### Task 1: Classification des ingrédients en catégories d'achat

**Files:**
- Create: `backend/app/services/cuisine/store_categories.py`
- Test: `backend/tests/test_cuisine/test_store_categories.py`

**Interfaces:**
- Consumes: `app.services.sante.adonis_pricing.PRODUCE_MAP` (dict existant, clé = nom FR, valeur `{"kw": [...], "edible": float, ...}`)
- Produces: `categorie_achat(ingredient: str) -> str | None` et `search_keywords(ingredient: str) -> list[str]`, utilisés par Task 2.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cuisine/test_store_categories.py
"""TDD — classification des ingrédients en catégories d'achat (Pantry/Viandes/
Fruits&Légumes/Tofu-Protéines) pour la comparaison de prix multi-magasins."""
from __future__ import annotations

from app.services.cuisine.store_categories import categorie_achat, search_keywords


def test_pantry_item_classified():
    assert categorie_achat("Riz basmati (sec)") == "pantry"
    assert search_keywords("Riz basmati (sec)") == ["basmati rice"]


def test_viande_volume_item_classified():
    assert categorie_achat("Poitrine de poulet") == "viande_volume"


def test_viande_noble_item_classified():
    assert categorie_achat("Saumon atlantique") == "viande_noble"


def test_tofu_proteines_item_classified():
    assert categorie_achat("Tofu ferme") == "tofu_proteines"


def test_fruits_legumes_reuses_adonis_produce_map():
    # "Banane" est dans PRODUCE_MAP (adonis_pricing.py) -> classé fruits_legumes
    assert categorie_achat("Banane") == "fruits_legumes"
    assert search_keywords("Banane") == ["banana"]


def test_unclassified_ingredient_returns_none():
    assert categorie_achat("Fromage cheddar") is None
    assert search_keywords("Fromage cheddar") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_cuisine/test_store_categories.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.cuisine.store_categories'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/cuisine/store_categories.py
"""Classification des ingrédients de la liste de courses en catégories
d'achat, avec mots-clés de recherche EN (vitrines Instacart/Lufa en anglais),
pour la comparaison de prix Super C / Adonis / Lufa. Voir
orchestration/a-faire/2026-07-06-lufa-superc-comparaison-prix-design.md.

Première version : seed manuel à corriger/étendre au fil de l'usage réel,
même philosophie que PRODUCE_MAP dans adonis_pricing.py (édite directement
le dict, aucun réimport nécessaire).
"""
from __future__ import annotations

from app.services.sante.adonis_pricing import PRODUCE_MAP

_PANTRY_KW: dict[str, list[str]] = {
    "Flocons d'avoine": ["oats", "oatmeal"],
    "Riz basmati (sec)": ["basmati rice"],
    "Riz brun (sec)": ["brown rice"],
    "Quinoa (sec)": ["quinoa"],
    "Pates (sec)": ["pasta"],
    "Lentilles seches": ["lentils"],
    "Pois chiches en conserve": ["chickpeas"],
    "Haricots noirs en conserve": ["black beans"],
    "Tomates concassees en conserve": ["diced tomatoes", "crushed tomatoes"],
    "Sel marin": ["sea salt"],
    "Huile d'olive extra-vierge": ["olive oil"],
    "Huile d'avocat": ["avocado oil"],
    "Huile de coco": ["coconut oil"],
    "Miel": ["honey"],
    "Sirop d'erable": ["maple syrup"],
    "Chocolat noir 72%": ["dark chocolate"],
    "Farine d'amande": ["almond flour"],
    "Tahini (sesame)": ["tahini"],
    "Graines de tournesol": ["sunflower seeds"],
    "Graines de lin": ["flax seed"],
    "Graines de chia": ["chia seed"],
    "Graines de courge": ["pumpkin seeds"],
    "Amandes": ["almonds"],
    "Noix de cajou": ["cashews"],
    "Noix de Grenoble": ["walnuts"],
    "Pacanes": ["pecans"],
    "Pistaches": ["pistachios"],
    "Arachides": ["peanuts"],
    "Noix de macadamia": ["macadamia"],
    "Pignons": ["pine nuts"],
    "Beurre d'arachide": ["peanut butter"],
    "Beurre d'amande": ["almond butter"],
}

_VIANDE_VOLUME_KW: dict[str, list[str]] = {
    "Poitrine de poulet": ["chicken breast"],
    "Cuisses de poulet desossees": ["chicken thighs", "boneless chicken thigh"],
    "Boeuf hache extra-maigre 5%": ["ground beef", "extra lean ground beef"],
    "Dinde hachee": ["ground turkey"],
    "Thon pale en conserve": ["canned tuna", "light tuna"],
    "Sardines en conserve": ["sardines"],
    "Maquereau": ["mackerel"],
    "Bacon": ["bacon"],
    "Crevettes cuites": ["cooked shrimp"],
}

_VIANDE_NOBLE_KW: dict[str, list[str]] = {
    "Bifteck de boeuf (faux-filet)": ["striploin steak", "sirloin steak"],
    "Filet de porc": ["pork tenderloin"],
    "Saumon atlantique": ["atlantic salmon", "salmon fillet"],
    "Saumon fume": ["smoked salmon"],
    "Tilapia": ["tilapia"],
    "Truite arc-en-ciel": ["rainbow trout"],
}

_TOFU_PROTEINES_KW: dict[str, list[str]] = {
    "Tofu ferme": ["firm tofu"],
    "Houmous": ["hummus"],
    "Boisson de soja": ["soy beverage", "soy milk"],
    "Whey protein (Inshape)": ["whey protein"],
    "Clear whey isolat (Inshape)": ["clear whey"],
    "Mass gainer chocolat (Inshape)": ["mass gainer"],
    "Barre proteinee + vitamines (Inshape)": ["protein bar"],
    "Pancakes proteines chocolat (Inshape)": ["protein pancake"],
    "Pate a tartiner proteinee cacao-noisettes (Inshape)": ["protein spread"],
    "Beurre de cacahuetes (Inshape)": ["peanut butter"],
    "Whey Leanfit vanille (Costco)": ["whey protein vanilla"],
    "Whey Gold Standard banane (ON)": ["gold standard whey banana"],
    "Mass gainer Serious Mass banane (ON)": ["serious mass banana"],
    "Clear whey + collagene pomme-framboise (ON)": ["clear whey collagen"],
    "Barre proteinee chocolate berry crunch (ON)": ["protein bar berry"],
    "Barre proteinee chocolate sea salt crunch (ON)": ["protein bar sea salt"],
    "Protein hot chocolate (ON)": ["protein hot chocolate"],
}

# Catégorie -> {nom FR: mots-clés EN}. "fruits_legumes" réutilise PRODUCE_MAP
# (adonis_pricing.py) comme source de vérité, pas de duplication.
_CATEGORY_KW: dict[str, dict[str, list[str]]] = {
    "pantry": _PANTRY_KW,
    "viande_volume": _VIANDE_VOLUME_KW,
    "viande_noble": _VIANDE_NOBLE_KW,
    "tofu_proteines": _TOFU_PROTEINES_KW,
    "fruits_legumes": {fr: spec["kw"] for fr, spec in PRODUCE_MAP.items()},
}


def categorie_achat(ingredient: str) -> str | None:
    """Catégorie d'achat de `ingredient` (nom FR exact, ex. "Tofu ferme"), ou
    None si non classifié (comportement rayon simple inchangé, pas de badge
    magasin)."""
    for categorie, kw_map in _CATEGORY_KW.items():
        if ingredient in kw_map:
            return categorie
    return None


def search_keywords(ingredient: str) -> list[str]:
    """Mots-clés EN à chercher dans les vitrines scrapées pour `ingredient`,
    ou liste vide si non classifié."""
    for kw_map in _CATEGORY_KW.values():
        if ingredient in kw_map:
            return kw_map[ingredient]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_cuisine/test_store_categories.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cuisine/store_categories.py backend/tests/test_cuisine/test_store_categories.py
git commit -m "feat(cuisine): classification ingrédients en catégories d'achat (Pantry/Viandes/Tofu)"
```

---

### Task 2: Service de comparaison de prix (règle par catégorie)

**Files:**
- Create: `backend/app/services/cuisine/store_pricing.py`
- Test: `backend/tests/test_cuisine/test_store_pricing.py`

**Interfaces:**
- Consumes: `store_categories.categorie_achat(str) -> str | None`, `store_categories.search_keywords(str) -> list[str]` (Task 1); `app.core.config.settings.imports_dir`, `settings.data_dir` (déjà utilisés par `adonis_pricing.py`).
- Produces: `recommend_store(ingredient: str) -> dict | None` (`{"magasin": str, "prix_estime": float, "promo": bool}`), `apply_recommendations(items: list[dict]) -> list[dict]`, `refresh_all_if_stale(max_age_h: float = 12.0) -> None` — utilisés par Task 3 et Task 4.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_cuisine/test_store_pricing.py
"""TDD — comparaison de prix Super C / Adonis / Lufa pour la liste de courses.

Seule la logique pure (catégorisation, matching, règle de comparaison) est
testée ; le rafraîchissement (scrape navigateur) est best-effort, comme pour
adonis_pricing.py — voir _cache_age_seconds/refresh_if_stale, non testés ici.
"""
from __future__ import annotations

from app.services.cuisine import store_pricing


def _fake_loader(data: dict[str, list[dict]]):
    def loader(store: str) -> list[dict]:
        return data.get(store, [])
    return loader


def test_pantry_compares_superc_vs_adonis_cheapest_wins(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Basmati Rice", "price": 3.99}],
        "adonis": [{"name": "Basmati Rice", "price": 4.49}],
    }))
    rec = store_pricing.recommend_store("Riz basmati (sec)")
    assert rec == {"magasin": "Super C", "prix_estime": 3.99, "promo": False}


def test_viande_noble_excludes_superc_even_if_cheapest(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Atlantic Salmon", "price": 1.0}],   # jamais comparé pour cette catégorie
        "adonis": [{"name": "Atlantic Salmon", "price": 9.0}],
        "lufa": [{"name": "Atlantic Salmon", "price": 8.5}],
    }))
    rec = store_pricing.recommend_store("Saumon atlantique")
    assert rec == {"magasin": "Lufa", "prix_estime": 8.5, "promo": False}


def test_fruits_legumes_exception_items_always_superc_no_comparison(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Sweet Potato", "price": 5.0}],
        "adonis": [{"name": "Sweet Potato", "price": 0.5}],
        "lufa": [{"name": "Sweet Potato", "price": 0.4}],
    }))
    rec = store_pricing.recommend_store("Patate douce")
    assert rec == {"magasin": "Super C", "prix_estime": 5.0, "promo": False}


def test_superc_flyer_price_beats_regular_and_flags_promo(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Ground Turkey", "price": 6.0}],
        "superc_flyer": [{"name": "Ground Turkey", "price": 3.5}],
        "adonis": [{"name": "Ground Turkey", "price": 5.0}],
    }))
    rec = store_pricing.recommend_store("Dinde hachee")
    assert rec == {"magasin": "Super C", "prix_estime": 3.5, "promo": True}


def test_unclassified_ingredient_returns_none(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({}))
    assert store_pricing.recommend_store("Fromage cheddar") is None


def test_no_match_in_either_store_returns_none(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Something else", "price": 1.0}],
        "adonis": [],
    }))
    assert store_pricing.recommend_store("Riz basmati (sec)") is None


def test_apply_recommendations_annotates_without_mutating_input(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Basmati Rice", "price": 3.99}],
        "adonis": [{"name": "Basmati Rice", "price": 4.49}],
    }))
    items = [{"ingredient": "Riz basmati (sec)", "quantite": 500, "unite": "g", "rayon": "Épicerie"}]
    out = store_pricing.apply_recommendations(items)
    assert out[0]["magasin_recommande"] == "Super C"
    assert out[0]["prix_estime"] == 3.99
    assert out[0]["promo"] is False
    assert "magasin_recommande" not in items[0]   # ne mute pas l'original


def test_apply_recommendations_skips_item_on_error(monkeypatch):
    def boom(store: str) -> list[dict]:
        raise RuntimeError("cache corrompu")
    monkeypatch.setattr(store_pricing, "load_cached_items", boom)
    items = [{"ingredient": "Riz basmati (sec)", "quantite": 500, "unite": "g", "rayon": "Épicerie"}]
    out = store_pricing.apply_recommendations(items)
    assert "magasin_recommande" not in out[0]   # best-effort : pas de crash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_cuisine/test_store_pricing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.cuisine.store_pricing'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/cuisine/store_pricing.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_cuisine/test_store_pricing.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cuisine/store_pricing.py backend/tests/test_cuisine/test_store_pricing.py
git commit -m "feat(cuisine): service de comparaison de prix Super C/Adonis/Lufa par catégorie"
```

---

### Task 3: Intégration dans `compute_shopping()`

**Files:**
- Modify: `backend/app/services/cuisine/shopping_list.py` (fonction `compute_shopping`, lignes 149-170)
- Modify: `backend/tests/test_cuisine/test_shopping.py`

**Interfaces:**
- Consumes: `store_pricing.apply_recommendations(list[dict]) -> list[dict]` (Task 2)
- Produces: `compute_shopping(...)` retourne désormais des dicts pouvant contenir `magasin_recommande`/`prix_estime`/`promo` en plus des clés existantes (`ingredient`, `quantite`, `unite`, `rayon`, `disponible`) — consommé par Task 5 (frontend).

- [ ] **Step 1: Write the failing test**

```python
# À ajouter dans backend/tests/test_cuisine/test_shopping.py
from unittest.mock import patch

from app.models.cuisine import MealPlanEntry, Recipe, RecipeIngredient
from app.services.cuisine.shopping_list import compute_shopping


def test_compute_shopping_applies_store_recommendations(mem_session):
    recipe = Recipe(titre="Riz aux légumes")
    mem_session.add(recipe)
    mem_session.commit()
    mem_session.refresh(recipe)
    mem_session.add(RecipeIngredient(recipe_id=recipe.id, nom_libre="Riz basmati (sec)", quantite=200, unite="g"))
    mem_session.add(MealPlanEntry(semaine="2026-07-06", jour=0, repas="diner", recipe_id=recipe.id))
    mem_session.commit()

    with patch(
        "app.services.cuisine.shopping_list.store_pricing.apply_recommendations",
        side_effect=lambda items: [
            {**it, "magasin_recommande": "Super C", "prix_estime": 3.99, "promo": False} for it in items
        ],
    ):
        out = compute_shopping(mem_session, "2026-07-06")

    assert out[0]["magasin_recommande"] == "Super C"
    assert out[0]["prix_estime"] == 3.99


def test_compute_shopping_survives_store_pricing_failure(mem_session):
    recipe = Recipe(titre="Riz aux légumes")
    mem_session.add(recipe)
    mem_session.commit()
    mem_session.refresh(recipe)
    mem_session.add(RecipeIngredient(recipe_id=recipe.id, nom_libre="Riz basmati (sec)", quantite=200, unite="g"))
    mem_session.add(MealPlanEntry(semaine="2026-07-06", jour=0, repas="diner", recipe_id=recipe.id))
    mem_session.commit()

    with patch(
        "app.services.cuisine.shopping_list.store_pricing.apply_recommendations",
        side_effect=RuntimeError("cache corrompu"),
    ):
        out = compute_shopping(mem_session, "2026-07-06")   # ne doit pas lever

    assert out[0]["ingredient"] == "Riz basmati (sec)"
    assert "magasin_recommande" not in out[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_cuisine/test_shopping.py -v -k store_recommendations`
Expected: FAIL — `compute_shopping` output has no `magasin_recommande` key (assertion error), or `AttributeError` (no `store_pricing` attribute on the module yet).

- [ ] **Step 3: Modify `compute_shopping`**

In `backend/app/services/cuisine/shopping_list.py`, add the import near the top (after the existing imports) and update `compute_shopping`:

```python
from app.services.cuisine import store_pricing
```

Replace the `compute_shopping` function body's final `return` (currently `return apply_inventaire(items, inventaire)`, lines ~163-170) with:

```python
def compute_shopping(
    session: Session, semaine: str, jours: list[int] | None = None,
    csv_path: Optional[Path] = None,
) -> list[dict]:
    """Liste de courses calculée à la volée, avec déduction de l'inventaire.

    Déduit ce qu'on possède déjà : la ligne 'QuantiteDispo' d'aliments.csv ET le
    garde-manger (data/cuisine_pantry.json) — un ingrédient présent au garde-manger
    réduit (ou supprime) la quantité à acheter. Annote ensuite chaque item restant
    avec un magasin recommandé (Super C/Adonis/Lufa) + prix estimé, en best-effort
    (voir store_pricing.py) : un échec de comparaison n'empêche jamais la liste.
    """
    q = select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)
    if jours is not None:
        q = q.where(MealPlanEntry.jour.in_(jours))  # type: ignore[attr-defined]
    items = _aggregate(session, list(session.exec(q).all()))
    inventaire = load_inventaire(csv_path)
    try:
        from app.services.cuisine import pantry as pantry_svc
        for nom, qte in pantry_to_inventaire(pantry_svc.list_items()).items():
            inventaire[nom] = inventaire.get(nom, 0.0) + qte
    except Exception:
        pass  # best-effort : le garde-manger ne casse jamais la liste
    items = apply_inventaire(items, inventaire)
    try:
        items = store_pricing.apply_recommendations(items)
    except Exception:
        pass  # best-effort : la comparaison magasin ne casse jamais la liste
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_cuisine/test_shopping.py -v`
Expected: PASS (all tests, including the 2 new ones)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cuisine/shopping_list.py backend/tests/test_cuisine/test_shopping.py
git commit -m "feat(cuisine): compute_shopping annote chaque item avec magasin recommandé + prix"
```

---

### Task 4: Rafraîchissement best-effort au démarrage du backend

**Files:**
- Modify: `backend/app/main.py` (fonction `lifespan`, après le bloc Ollama autostart lignes 58-70)
- Modify: `backend/tests/conftest.py` (fixture `_isolate_external_side_effects`)

**Interfaces:**
- Consumes: `store_pricing.refresh_all_if_stale(max_age_h: float = 12.0) -> None` (Task 2)

- [ ] **Step 1: Add the env-var guard to the test isolation fixture**

In `backend/tests/conftest.py`, in `_isolate_external_side_effects`, add next to the existing `ADONIS_PRODUCE_PRICING` line:

```python
    monkeypatch.setenv("ADONIS_PRODUCE_PRICING", "0")
    monkeypatch.setenv("STORE_PRICING_REFRESH", "0")
```

This prevents any test that spins up the FastAPI app (and therefore its `lifespan`) from spawning real scraper subprocesses, mirroring the existing Adonis guard.

- [ ] **Step 2: Wire the background refresh into `lifespan`**

In `backend/app/main.py`, after the Ollama autostart block (after line 70, before `# Démarrer APScheduler`), add:

```python
    # Rafraîchir les prix Super C/Adonis/Lufa si périmés — en arrière-plan,
    # ne bloque pas le boot (STORE_PRICING_REFRESH=0 désactive, cf. tests).
    import threading

    def _refresh_store_pricing() -> None:
        try:
            from app.services.cuisine.store_pricing import refresh_all_if_stale
            refresh_all_if_stale()
        except Exception as exc:  # pragma: no cover — défensif
            log.warning("Rafraîchissement prix magasins: %s", exc)

    threading.Thread(target=_refresh_store_pricing, daemon=True).start()
```

- [ ] **Step 3: Verify existing tests still pass (no behavior change expected)**

Run: `cd backend && uv run pytest tests/ -v -k "conftest or main or lifespan"`
Expected: PASS — this step has no dedicated new test (background thread side-effects aren't asserted on directly, consistent with how the existing Ollama autostart thread is untested); the goal is a regression check that adding the guard didn't break anything else.

Run the full suite once to confirm nothing else regressed:
Run: `cd backend && uv run pytest tests/ -q`
Expected: PASS (same pass count as before this task, plus Tasks 1-3's new tests)

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py
git commit -m "feat(cuisine): rafraîchissement best-effort des prix magasins au démarrage backend"
```

---

### Task 5: Scraper Super C — vitrine Instacart

**Files:**
- Create: `frontend/.superc_scrape.mjs`

**Interfaces:**
- Produces: `data/imports/Cuisine/superc.json` (`{source, scraped_at, count, items: [{name, id, href, price, price_unit, unit_price, unit, original_price, on_sale, discount_pct, format, query}]}`) — consommé par `store_pricing.load_cached_items("superc")` (Task 2).

- [ ] **Step 1: Write the scraper**

```javascript
// frontend/.superc_scrape.mjs
// Scrape la vitrine "Super C powered by Instacart" (instacart.ca/store/super-c),
// même pattern que .adonis_scrape.mjs. Les termes de recherche sont passés en
// argument (dérivés de la liste de courses de la semaine par le backend) :
// évite une liste figée, reste rapide et à jour avec le plan de repas courant.
//
// Usage:  node .superc_scrape.mjs <sortie.json> <terme1> <terme2> ...
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const STORE = 'https://www.instacart.ca/store/super-c';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/superc.json');
const TERMS = process.argv.slice(3);

const EXTRACT = () => {
  const cards = [...document.querySelectorAll('a[data-item-card-button="true"]')];
  const num = (s) => (s ? parseFloat(s.replace(',', '.')) : null);
  return cards.slice(0, 14).map((c) => {
    const img = c.querySelector('img[data-testid="item-card-image"]');
    const name = img ? (img.getAttribute('alt') || '').trim() : '';
    const t = (c.innerText || '').replace(/\s+/g, ' ').trim();
    const href = (c.getAttribute('href') || '').split('?')[0];
    const id = (href.match(/\/products\/(\d+)/) || [])[1] || null;
    const cur = t.match(/Current price:\s*\$(\d+[.,]\d{2})\s*([a-z]+)?/i) || t.match(/\$(\d+[.,]\d{2})\s*(each|lb|kg|g|ea)?/i);
    const orig = t.match(/Original Price:\s*\$(\d+[.,]\d{2})/i);
    const unit = t.match(/\$(\d+[.,]\d{2})\s*\/\s*(kg|lb|g|l|ml|each|ea)/i);
    const sale = /(\d+)%\s*off/i.exec(t);
    const fmt = (t.match(/About\s+[\d.,]+\s*(kg|lb|g)\s*each/i) || [])[0]
      || (t.match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack)\b/i) || [])[0] || '';
    return {
      name, id, href,
      price: cur ? num(cur[1]) : null,
      price_unit: cur && cur[2] ? cur[2].toLowerCase() : null,
      unit_price: unit ? num(unit[1]) : null,
      unit: unit ? unit[2].toLowerCase() : null,
      original_price: orig ? num(orig[1]) : null,
      on_sale: !!orig || !!sale,
      discount_pct: sale ? parseInt(sale[1], 10) : null,
      format: fmt,
    };
  }).filter((x) => x.name || x.href);
};

const b = await chromium.launch({ executablePath: EDGE, headless: true });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'en-CA' });
const page = await ctx.newPage();
try {
  await page.goto(`${STORE}/storefront`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(6000);
} catch { /* best-effort */ }

const byKey = new Map();
for (const term of TERMS) {
  try {
    await page.goto(`${STORE}/s?k=${encodeURIComponent(term)}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2600);
    let items = await page.evaluate(EXTRACT);
    if (items.length === 0) {
      await page.waitForTimeout(3500);
      items = await page.evaluate(EXTRACT);
    }
    for (const it of items) {
      const key = it.id || it.name.toLowerCase();
      if (!byKey.has(key)) byKey.set(key, { ...it, query: term });
    }
    console.error(`[superc] "${term}" -> ${items.length} (total ${byKey.size})`);
  } catch (e) {
    console.error(`[superc] "${term}" ERREUR ${String(e).slice(0, 100)}`);
  }
}
await b.close();

const out = [...byKey.values()].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'instacart.ca/store/super-c (search)', scraped_at: new Date().toISOString(), count: out.length, items: out }, null, 2));
console.error(`[superc] ${out.length} items écrits dans ${OUT}`);
```

- [ ] **Step 2: Run it manually to verify the output shape**

Run: `cd frontend && node .superc_scrape.mjs ../data/imports/Cuisine/superc.json "basmati rice" "ground turkey"`
Expected: prints `[superc] "..." -> N (total M)` lines to stderr, then `[superc] M items écrits dans ...`; `data/imports/Cuisine/superc.json` exists and contains a JSON object with a non-empty `items` array (requires Edge installed and network access — best-effort, matches the existing Adonis scraper's manual verification approach, no automated test).

- [ ] **Step 3: Commit**

```bash
git add frontend/.superc_scrape.mjs
git commit -m "feat(cuisine): scraper Super C (vitrine Instacart)"
```

---

### Task 6: Scraper Super C — circulaire (flyer)

**Files:**
- Create: `frontend/.superc_flyer_scrape.mjs`

**Interfaces:**
- Produces: `data/imports/Cuisine/superc_flyer.json` (même format que Task 5) — consommé par `store_pricing._best_price("superc", ...)` (Task 2, branche circulaire).

- [ ] **Step 1: Write the scraper**

```javascript
// frontend/.superc_flyer_scrape.mjs
// Scrape la circulaire hebdo Super C (superc.ca/circulaire) pour capter les
// rabais ponctuels non reflétés sur Instacart (ex. items en solde cette
// semaine seulement). Format JSON identique aux autres scrapers cuisine :
// store_pricing.py compare ce cache au prix Instacart courant et retient le
// moins cher (voir _best_price, branche "superc").
//
// Usage:  node .superc_flyer_scrape.mjs <sortie.json>
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const FLYER_URL = 'https://www.superc.ca/circulaire';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/superc_flyer.json');

const EXTRACT = () => {
  const cards = [...document.querySelectorAll('[class*="product-tile"], [class*="flyer-item"]')];
  const num = (s) => (s ? parseFloat(s.replace(',', '.')) : null);
  return cards.map((c) => {
    const t = (c.innerText || '').replace(/\s+/g, ' ').trim();
    const nameEl = c.querySelector('[class*="product-title"], [class*="item-name"], h3, h4');
    const name = (nameEl ? nameEl.textContent : t.split('\n')[0] || '').trim();
    const cur = t.match(/\$(\d+[.,]\d{2})/);
    const unit = t.match(/\$(\d+[.,]\d{2})\s*\/\s*(kg|lb|g|l|ml|each|ea)/i);
    const fmt = (t.match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack)\b/i) || [])[0] || '';
    return {
      name,
      href: null,
      price: cur ? num(cur[1]) : null,
      price_unit: null,
      unit_price: unit ? num(unit[1]) : null,
      unit: unit ? unit[2].toLowerCase() : null,
      original_price: null,
      on_sale: true,   // tout item de circulaire est par définition une promo
      discount_pct: null,
      format: fmt,
    };
  }).filter((x) => x.name && x.price != null);
};

const b = await chromium.launch({ executablePath: EDGE, headless: true });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'fr-CA' });
const page = await ctx.newPage();

let items = [];
try {
  await page.goto(FLYER_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(4000);
  items = await page.evaluate(EXTRACT);
  console.error(`[superc_flyer] ${items.length} items extraits de la circulaire`);
} catch (e) {
  console.error(`[superc_flyer] ERREUR ${String(e).slice(0, 200)}`);
}
await b.close();

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'superc.ca/circulaire', scraped_at: new Date().toISOString(), count: items.length, items }, null, 2));
console.error(`[superc_flyer] ${items.length} items écrits dans ${OUT}`);
```

- [ ] **Step 2: Run it manually to verify the output shape**

Run: `cd frontend && node .superc_flyer_scrape.mjs ../data/imports/Cuisine/superc_flyer.json`
Expected: `data/imports/Cuisine/superc_flyer.json` exists with a JSON object containing an `items` array. **Note:** the circular's actual DOM structure (`[class*="product-tile"]` selectors) is a best guess based on common flyer-site markup — if the real page uses different class names, inspect `superc.ca/circulaire` in a browser devtools session and adjust the `EXTRACT` selectors accordingly before relying on this in production. This is expected manual tuning, not a plan gap — flag it to the user if the first real run returns 0 items.

- [ ] **Step 3: Commit**

```bash
git add frontend/.superc_flyer_scrape.mjs
git commit -m "feat(cuisine): scraper circulaire Super C (promos hebdo)"
```

---

### Task 7: Scraper Lufa — marketplace avec session persistante

**Files:**
- Create: `frontend/.lufa_scrape.mjs`

**Interfaces:**
- Produces: `data/imports/Cuisine/lufa.json` (même format que Task 5) — consommé par `store_pricing.load_cached_items("lufa")` (Task 2).

- [ ] **Step 1: Write the scraper**

```javascript
// frontend/.lufa_scrape.mjs
// Scrape le marché Lufa (lufa.com) — nécessite un compte connecté avec un
// point relais choisi pour voir prix/dispo, contrairement aux vitrines
// Instacart. Utilise un PROFIL EDGE PERSISTANT (launchPersistentContext) :
// connecte-toi une fois manuellement dans ce profil (voir instructions
// d'exécution), la session est réutilisée par tous les runs suivants.
//
// Usage:  node .lufa_scrape.mjs <sortie.json> <terme1> <terme2> ...
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
// Profil dédié (séparé du profil Edge par défaut), gitignoré comme les caches
// data/imports/*. Créé automatiquement au premier lancement.
const PROFILE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '.lufa_profile');
const MARKET_URL = 'https://montreal.lufa.com/en/marketplace';
const OUT = process.argv[2] || path.resolve('../data/imports/Cuisine/lufa.json');
const TERMS = process.argv.slice(3);

const EXTRACT = () => {
  const cards = [...document.querySelectorAll('[class*="product-card"], [class*="ProductCard"]')];
  const num = (s) => (s ? parseFloat(s.replace(',', '.')) : null);
  return cards.map((c) => {
    const t = (c.innerText || '').replace(/\s+/g, ' ').trim();
    const nameEl = c.querySelector('[class*="product-name"], [class*="title"], h3, h4');
    const name = (nameEl ? nameEl.textContent : t.split('\n')[0] || '').trim();
    const href = (c.querySelector('a') || {}).href || null;
    const cur = t.match(/\$(\d+[.,]\d{2})/);
    const unit = t.match(/\$(\d+[.,]\d{2})\s*\/\s*(kg|lb|g|l|ml|each|ea|un)/i);
    const sale = /(\d+)%\s*off|promo/i.test(t);
    const fmt = (t.match(/\b\d+(?:[.,]\d+)?\s*(?:x\s*\d+)?\s*(kg|g|lb|oz|l|ml|ct|pack|un)\b/i) || [])[0] || '';
    return {
      name, href,
      price: cur ? num(cur[1]) : null,
      price_unit: null,
      unit_price: unit ? num(unit[1]) : null,
      unit: unit ? unit[2].toLowerCase() : null,
      original_price: null,
      on_sale: sale,
      discount_pct: null,
      format: fmt,
    };
  }).filter((x) => x.name && x.price != null);
};

fs.mkdirSync(PROFILE_DIR, { recursive: true });
const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
  executablePath: EDGE, headless: true,
  viewport: { width: 1366, height: 1000 }, locale: 'en-CA',
});
const page = ctx.pages()[0] || await ctx.newPage();

const byKey = new Map();
try {
  await page.goto(MARKET_URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(4000);
  if (TERMS.length === 0) {
    const items = await page.evaluate(EXTRACT);
    for (const it of items) byKey.set(it.href || it.name.toLowerCase(), { ...it, query: null });
  } else {
    for (const term of TERMS) {
      try {
        await page.goto(`${MARKET_URL}?search=${encodeURIComponent(term)}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(2600);
        const items = await page.evaluate(EXTRACT);
        for (const it of items) {
          const key = it.href || it.name.toLowerCase();
          if (!byKey.has(key)) byKey.set(key, { ...it, query: term });
        }
        console.error(`[lufa] "${term}" -> ${items.length} (total ${byKey.size})`);
      } catch (e) {
        console.error(`[lufa] "${term}" ERREUR ${String(e).slice(0, 100)}`);
      }
    }
  }
} catch (e) {
  console.error(`[lufa] ERREUR navigation marketplace: ${String(e).slice(0, 200)} — session Lufa probablement non connectée, voir instructions de connexion manuelle`);
}
await ctx.close();

const out = [...byKey.values()].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ source: 'lufa.com/marketplace (session persistante)', scraped_at: new Date().toISOString(), count: out.length, items: out }, null, 2));
console.error(`[lufa] ${out.length} items écrits dans ${OUT}`);
```

- [ ] **Step 2: One-time manual login (required before this scraper can return real data)**

Run once, headed (not headless), to log in manually and select your point relais — the session persists in `.lufa_profile/` for all future headless runs:

```bash
cd frontend && node -e "
import('playwright-core').then(async ({ chromium }) => {
  const ctx = await chromium.launchPersistentContext('.lufa_profile', {
    executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    headless: false,
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://montreal.lufa.com/en/login');
  console.log('Connecte-toi et choisis ton point relais dans la fenêtre Edge, puis ferme-la.');
});
"
```

Expected: an Edge window opens; log in and pick your point relais; close the window when done. `.lufa_profile/` now contains the persisted session.

- [ ] **Step 3: Run the scraper to verify the output shape**

Run: `cd frontend && node .lufa_scrape.mjs ../data/imports/Cuisine/lufa.json "atlantic salmon"`
Expected: `data/imports/Cuisine/lufa.json` exists with a non-empty `items` array. **Note, same caveat as Task 6:** the `[class*="product-card"]` selectors are a best guess — inspect the real marketplace DOM and adjust `EXTRACT` if the first run returns 0 items despite a valid logged-in session.

- [ ] **Step 4: Add `.lufa_profile/` to `.gitignore`**

Check `.gitignore` for an existing `data/imports/*`-style entry and add, if not already covered by a broader pattern:

```
frontend/.lufa_profile/
```

- [ ] **Step 5: Commit**

```bash
git add frontend/.lufa_scrape.mjs .gitignore
git commit -m "feat(cuisine): scraper Lufa marketplace (session Edge persistante)"
```

---

### Task 8: Badge magasin dans l'UI liste de courses

**Files:**
- Modify: `frontend/lib/cuisine.ts` (type `ShoppingItem`, ligne 112)
- Modify: `frontend/components/cuisine/CoursesTab.tsx`

**Interfaces:**
- Consumes: `magasin_recommande?: string`, `prix_estime?: number`, `promo?: boolean` sur chaque item retourné par `/shopping-list/preview` (Task 3).

- [ ] **Step 1: Extend the `ShoppingItem` type**

In `frontend/lib/cuisine.ts`, replace line 112:

```typescript
export type ShoppingItem = { ingredient: string; quantite: number; unite: string; rayon: string }
```

with:

```typescript
export type ShoppingItem = {
  ingredient: string
  quantite: number
  unite: string
  rayon: string
  magasin_recommande?: string
  prix_estime?: number
  promo?: boolean
}
```

- [ ] **Step 2: Render the store badge in `CoursesTab.tsx`**

In `frontend/components/cuisine/CoursesTab.tsx`, inside the item row (after the quantity `<span>`, currently lines 131-133):

```tsx
                        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
                          {fmtQte(it)}
                        </span>
```

add immediately after it (before the closing `</button>`):

```tsx
                        {it.magasin_recommande && (
                          <span
                            className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                              it.promo
                                ? 'bg-[var(--warning-bg,#fef3c7)] text-[var(--warning-fg,#92400e)]'
                                : 'bg-[var(--muted)] text-[var(--muted-foreground)]'
                            }`}
                          >
                            {it.magasin_recommande}
                            {it.prix_estime != null ? ` · ${it.prix_estime.toFixed(2)}$` : ''}
                          </span>
                        )}
```

- [ ] **Step 3: Manually verify in the browser**

Run the app (`cd frontend && npx concurrently ...` per the project's usual dev launch, or just `next dev` if the backend is already running), open the Courses tab, confirm:
- Items with a store recommendation show a badge (`Super C · 3.99$` style).
- Items without one (unclassified ingredients, or no cache yet) render exactly as before — no layout break.
- A `promo: true` item's badge is visually distinct (amber background) from a regular recommendation.

Expected: no console errors, badges render only where `magasin_recommande` is present, existing checkbox/strike-through behavior unaffected.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/cuisine.ts frontend/components/cuisine/CoursesTab.tsx
git commit -m "feat(cuisine): badge magasin recommandé + prix dans la liste de courses"
```

---

## Self-Review Notes

- **Spec coverage:** scrapers (Task 5-7), catégorisation (Task 1), règle de comparaison incl. exception F&L et circulaire Super C (Task 2), intégration liste de courses (Task 3), rafraîchissement démarrage (Task 4), UI (Task 8) — all design sections covered. `aliments.csv`/nutrition optimizer explicitly out of scope, untouched.
- **Type consistency:** `recommend_store` return shape (`{"magasin", "prix_estime", "promo"}`) matches `apply_recommendations`'s injected keys (`magasin_recommande`, `prix_estime`, `promo`) matches the frontend `ShoppingItem` fields — verified across Tasks 2, 3, 8.
- **Known follow-up (not a gap, flagged in-line):** the flyer/marketplace DOM selectors in Tasks 6-7 are best-guess and will likely need one round of manual selector tuning against the real live sites, same as any first-time scraper — this mirrors how `.adonis_scrape.mjs` itself was presumably tuned once against the real Instacart DOM.
