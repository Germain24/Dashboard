# Phase 1 — Liste de courses en Super C seul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire recommander Super C pour toutes les catégories de la liste de courses, en supprimant la comparaison Adonis et l'exception fruits/légumes.

**Architecture:** Un seul module change — `store_pricing.py`. On aplatit `CATEGORY_STORES` en `{catégorie: "superc"}`, on retire l'exception `FRUITS_LEGUMES_SUPERC_ONLY`, et on réduit `recommend_store` au chemin mono-magasin (le chemin de comparaison à 2 magasins devient mort et est retiré). La logique promo circulaire (`_best_price` avec `superc` + `superc_flyer`) est conservée telle quelle.

**Tech Stack:** Python 3.13, pytest, monkeypatch (pas de scrape réel dans les tests).

## Global Constraints

- Best-effort partout : un cache manquant, un item non catégorisé ou une erreur ne casse jamais la liste de courses (`apply_recommendations` reste tolérant).
- Aucun autre magasin (Adonis, Lufa) comme source de prix pour les courses.
- La branche `store == "adonis"` de `load_cached_items` reste en place (dormante) — elle sera débranchée en Phase 2. Ne pas la supprimer ici.
- Conserver la gestion de promo circulaire (`superc_flyer`) dans `_best_price`.
- Réf spec : `orchestration/a-faire/2026-07-14-superc-unique-design.md` (Phase 1).

---

### Task 1: Recommander Super C pour toutes les catégories

**Files:**
- Modify: `backend/app/services/cuisine/store_pricing.py`
- Test: `backend/tests/test_cuisine/test_store_pricing.py`

**Interfaces:**
- Consumes: `store_categories.categorie_achat(ingredient) -> str | None`, `store_categories.search_keywords`, `_best_price(store, ingredient) -> tuple[float, bool] | None` (inchangés).
- Produces: `CATEGORY_STORES: dict[str, str]` (valeurs = un seul magasin) ; `recommend_store(ingredient) -> dict | None` renvoyant toujours `{"magasin": "Super C", "prix_estime": float, "promo": bool}` quand un prix est matché. `FRUITS_LEGUMES_SUPERC_ONLY` est supprimée.

Toutes les commandes `pytest` se lancent **depuis le dossier `backend/`**.

- [ ] **Step 1: Réécrire les tests pour le comportement Super C seul**

Dans `backend/tests/test_cuisine/test_store_pricing.py`, remplacer les 5 tests qui encodent l'ancien comportement (comparaison / Adonis / exception) par leurs équivalents Super C. Remplacer `test_pantry_compares_superc_vs_adonis_cheapest_wins`, `test_viande_noble_excludes_superc_even_if_cheapest`, `test_viande_noble_no_recommendation_when_adonis_has_no_match`, `test_fruits_legumes_exception_items_always_superc_no_comparison`, et `test_fruits_legumes_non_exception_uses_adonis_alone` par :

```python
def test_pantry_uses_superc(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Basmati Rice", "price": 3.99}],
    }))
    rec = store_pricing.recommend_store("Riz basmati (sec)")
    assert rec == {"magasin": "Super C", "prix_estime": 3.99, "promo": False}


def test_viande_noble_now_uses_superc(monkeypatch):
    # viande_noble comparait Adonis seul (Super C = éviter, ancien design).
    # Désormais tout passe par Super C.
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Atlantic Salmon", "price": 9.0}],
    }))
    rec = store_pricing.recommend_store("Saumon atlantique")
    assert rec == {"magasin": "Super C", "prix_estime": 9.0, "promo": False}


def test_viande_noble_no_recommendation_when_superc_has_no_match(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [],
    }))
    assert store_pricing.recommend_store("Saumon atlantique") is None


def test_fruits_legumes_uses_superc(monkeypatch):
    # L'exception "patate douce/oignon toujours Super C" est supprimée :
    # tout fruits_legumes passe par Super C de toute façon.
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Sweet Potato", "price": 5.0}],
    }))
    rec = store_pricing.recommend_store("Patate douce")
    assert rec == {"magasin": "Super C", "prix_estime": 5.0, "promo": False}


def test_fruits_legumes_banana_uses_superc(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Banana", "price": 0.31}],
    }))
    rec = store_pricing.recommend_store("Banane")
    assert rec == {"magasin": "Super C", "prix_estime": 0.31, "promo": False}
```

Dans `test_superc_flyer_price_beats_regular_and_flags_promo` et
`test_apply_recommendations_annotates_without_mutating_input`, supprimer la ligne
`"adonis": [...]` du dict passé à `_fake_loader` (elle n'est plus lue). Les assertions
restent identiques (résultat Super C inchangé).

Laisser tels quels : `test_unclassified_ingredient_returns_none`,
`test_no_match_in_either_store_returns_none`, et tous les tests
`_current_week_search_terms` / `refresh_*` (non affectés).

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `pytest tests/test_cuisine/test_store_pricing.py -v`
Expected: FAIL — `test_viande_noble_now_uses_superc` et `test_fruits_legumes_banana_uses_superc` échouent (le code actuel renvoie Adonis / None car `CATEGORY_STORES` pointe encore vers Adonis).

- [ ] **Step 3: Aplatir `CATEGORY_STORES` et retirer l'exception**

Dans `backend/app/services/cuisine/store_pricing.py`, remplacer le bloc `CATEGORY_STORES` (et son commentaire) ainsi que `FRUITS_LEGUMES_SUPERC_ONLY` par :

```python
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
```

Supprimer entièrement la constante `FRUITS_LEGUMES_SUPERC_ONLY = {...}` et son commentaire.

- [ ] **Step 4: Réduire `recommend_store` au chemin mono-magasin**

Remplacer toute la fonction `recommend_store` par :

```python
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
```

(Le chemin de comparaison à 2 magasins et la branche `FRUITS_LEGUMES_SUPERC_ONLY` disparaissent.) Ne pas toucher à `_best_price`, `load_cached_items`, `apply_recommendations`, ni aux fonctions de refresh.

- [ ] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `pytest tests/test_cuisine/test_store_pricing.py -v`
Expected: PASS (tous).

- [ ] **Step 6: Non-régression sur les modules voisins**

Run: `pytest tests/test_cuisine/test_store_categories.py tests/test_cuisine/test_shopping.py -v`
Expected: PASS (aucun de ces modules ne dépend de `CATEGORY_STORES` ; garde-fou de régression).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cuisine/store_pricing.py backend/tests/test_cuisine/test_store_pricing.py
git commit -m "feat(courses): recommander Super C seul (fin comparaison Adonis)"
```

---

## Self-Review

- **Couverture spec (Phase 1)** : `CATEGORY_STORES` tout Super C (Steps 3), exception supprimée (Step 3), `recommend_store` mono-magasin (Step 4), promo circulaire conservée (`_best_price` non touché), branche Adonis de `load_cached_items` laissée dormante (non touchée). ✅
- **Placeholders** : aucun — code réel à chaque step. ✅
- **Cohérence des types** : `CATEGORY_STORES: dict[str, str]` (valeurs `str`), `recommend_store` lit `CATEGORY_STORES[categorie]` comme `str` et l'indexe dans `_STORE_LABELS` — cohérent. ✅
