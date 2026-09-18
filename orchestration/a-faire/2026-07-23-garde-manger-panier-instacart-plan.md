# Garde-manger + panier Super C (Instacart) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. NOTE (2026-07-23) : subagents indisponibles (limite de dépense) → exécution **inline** par le contrôleur, tests réels lancés à chaque tâche.

**Goal:** Déclarer un garde-manger (stock déjà payé) qui priorise le stock dans l'optimiseur SANS déséquilibrer le repas et se déduit de la liste/du coût à payer ; puis remplir le panier Super C (Instacart) réel via Claude-in-Chrome.

**Architecture:** Phase 1 ajoute (a) un **bonus stock borné** dans `optimize_nutrition` (sous les poids macros/couverture → équilibre garanti), (b) une **déduction quantité-limitée** post-optimisation qui ne touche que le coût à payer (le ratio reste sur le coût catalogue ≠ 0). Phase 2 réutilise le matching mots-clés existant pour retrouver **le produit Instacart chiffré** par aliment + calcule les quantités (paquets), expose un `cart-plan`, et documente le remplissage live Claude-in-Chrome (best-effort, ajout seul, jamais de checkout).

**Tech Stack:** Python/FastAPI/SQLModel, SciPy SLSQP, pandas ; frontend Next.js/React Query/Tailwind ; Claude-in-Chrome MCP pour le remplissage.

## Global Constraints

- Spec : `orchestration/a-faire/2026-07-23-garde-manger-panier-instacart-design.md`.
- Branche active `chore/audit-quick-wins`, **pas d'isolation** (pas de worktree/branche dédiée).
- Tests backend depuis `backend/` via `./.venv/Scripts/python.exe -m pytest ...` ; frontend `npx vitest run` + `npx tsc --noEmit` + `npx eslint`.
- Commits FR, préfixe conventionnel, trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Garde-fous invariants** : le bonus stock ne doit JAMAIS l'emporter sur les contraintes dures (calories/protéines) ni la couverture micro ; le **coût du ratio reste le coût catalogue** (≠ 0), le garde-manger ne réduit que le coût à payer et la liste ; le panier est **cart-only** (jamais de checkout, ajout seul).
- Catalogue factice de test : réutiliser le `_fake_df()` **31 colonnes** de `test_fenetre_service.py` (l'optimiseur exige une colonne par micro de `DAILY_BASE_TARGETS_NUTRIENTS`).

---

## PHASE 1 — Garde-manger

### Task 1 : bonus stock borné dans `optimize_nutrition`

**Files:** Modify `backend/app/services/sante/optimizer.py` · Test `backend/tests/test_sante/test_pantry_bonus.py`

**Interfaces:** Produces `optimize_nutrition(..., pantry_names: set[str] | None = None)` — un terme de préférence borné récompense l'usage des aliments dont le nom ∈ `pantry_names`. Défaut None = comportement inchangé.

- [ ] **Step 1 — test (RED)**
```python
# backend/tests/test_sante/test_pantry_bonus.py
import pandas as pd
from app.services.sante.optimizer import optimize_nutrition


def _df():
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres"]
    # A et B nutritionnellement ~identiques et même prix ; seul le stock diffère.
    data = {"A": [100, 8, 2, 10, 1.0, 40, 3], "B": [100, 8, 2, 10, 1.0, 40, 3]}
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


def _t():
    return {"Calories": 300.0, "Protéines": 20.0, "Lipides": 6.0, "Glucides": 30.0,
            "Poids_Corps": 60.0, "Prix_Max": 30.0, "VitC": 100.0, "Fibres": 10.0}


def test_pantry_bonus_breaks_tie_toward_stock():
    df, t = _df(), _t()
    use = lambda p, n: sum(it["Quantite_g"] for it in p if it["Aliment"] == n)
    plan = optimize_nutrition(df, t, budget_max_daily=30.0, pantry_names={"A"})[0]
    assert use(plan, "A") > use(plan, "B")   # stock A préféré à égalité nutritionnelle


def test_pantry_bonus_default_noop():
    df, t = _df(), _t()
    a = optimize_nutrition(df, t, budget_max_daily=30.0, seed=1)[0]
    b = optimize_nutrition(df, t, budget_max_daily=30.0, seed=1, pantry_names=None)[0]
    g = lambda p: {it["Aliment"]: round(it["Quantite_g"], 3) for it in p}
    assert g(a) == g(b)
```

- [ ] **Step 2 — run RED** : `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_sante/test_pantry_bonus.py -v` → FAIL (`unexpected keyword 'pantry_names'`).

- [ ] **Step 3 — implémentation** dans `optimizer.py` :
  1. Ajouter le constant en tête (près de `DIVERSITY_WEIGHT`) :
     ```python
     # Bonus « déjà en stock » : petit gain par 100 g d'aliment du garde-manger utilisé.
     # Même échelle que la préférence taste (0..0.5) : départage vers le stock à valeur
     # nutritionnelle comparable, SANS jamais l'emporter sur macros (100-1000)/couverture (60).
     PANTRY_BONUS_WEIGHT = 0.3
     ```
  2. Signature : ajouter `pantry_names: Optional[set[str]] = None` à la fin.
  3. Après `taste_arr` : construire un masque stock aligné sur `food_names` :
     ```python
     pantry_arr = np.zeros(num_foods)
     if pantry_names:
         for i, name in enumerate(food_names):
             if name in pantry_names:
                 pantry_arr[i] = 1.0
     ```
  4. Dans `objective`, juste après le terme taste, retrancher le bonus stock :
     ```python
         # Bonus stock (négatif = récompense) — borné par PANTRY_BONUS_WEIGHT.
         error -= PANTRY_BONUS_WEIGHT * float(np.dot(x, pantry_arr))
     ```

- [ ] **Step 4 — run GREEN** : même commande → 2 passed. Puis garde-fou : `./.venv/Scripts/python.exe -m pytest tests/test_sante/ -q` → tout vert (aucune régression optimiseur).

- [ ] **Step 5 — commit** :
```bash
git add backend/app/services/sante/optimizer.py backend/tests/test_sante/test_pantry_bonus.py
git commit -m "feat(sante): bonus stock borne dans optimize_nutrition (garde-manger, equilibre preserve)"
```

---

### Task 2 : propager `pantry_names` dans `optimize_ratio`

**Files:** Modify `backend/app/services/sante/ratio_optimizer.py` · Test `backend/tests/test_sante/test_ratio_optimizer.py` (ajout)

**Interfaces:** `optimize_ratio(..., pantry_names: set[str] | None = None)` passe l'argument à chaque appel `optimize_nutrition`.

- [ ] **Step 1 — test (RED)** : ajouter à `test_ratio_optimizer.py` :
```python
def test_optimize_ratio_forwards_pantry_names(monkeypatch):
    import app.services.sante.ratio_optimizer as ro
    seen = {}
    real = ro.optimize_nutrition
    def spy(df, targets, **kw):
        seen["pantry"] = kw.get("pantry_names")
        return real(df, targets, **kw)
    monkeypatch.setattr(ro, "optimize_nutrition", spy)
    optimize_ratio(_df(), _targets(), budget_max_daily=20.0, pantry_names={"Legume"})
    assert seen["pantry"] == {"Legume"}
```

- [ ] **Step 2 — run RED** → FAIL (`unexpected keyword 'pantry_names'`).

- [ ] **Step 3 — implémentation** : signature `optimize_ratio(..., pantry_names: Optional[set[str]] = None, price_weights=...)` et dans la boucle : `optimize_nutrition(df, targets, budget_max_daily=..., seed=seed, price_weight=pw, micro_weight_mult=micro_weight_mult, pantry_names=pantry_names)`.

- [ ] **Step 4 — run GREEN** : `pytest tests/test_sante/test_ratio_optimizer.py -v` → tout vert.

- [ ] **Step 5 — commit** : `git commit -m "feat(sante): optimize_ratio propage pantry_names (garde-manger)"`

---

### Task 3 : chargement garde-manger + déduction (`pantry_fenetre.py`)

**Files:** Create `backend/app/services/sante/pantry_fenetre.py` · Test `backend/tests/test_sante/test_pantry_fenetre.py`

**Interfaces:**
- `load_pantry_grams(items: list[dict]) -> dict[str, float]` — convertit les items garde-manger (`{ingredient, quantite, unite}`) en `{aliment: grammes}` (g/kg→g ; unité/ml ignorées ou 1:1). Somme les doublons.
- `apply_pantry_deduction(shopping_list: list[dict], pantry_g: dict[str, float]) -> tuple[list[dict], float]` — pour chaque item, `dispo_g = min(quantite_g, stock)`, `a_acheter_g = quantite_g - dispo_g`, `prix` recalé au prorata de `a_acheter_g` ; item entièrement en stock → retiré. Retourne `(items_annotés, cout_a_payer)`.

- [ ] **Step 1 — test (RED)**
```python
# backend/tests/test_sante/test_pantry_fenetre.py
import pytest
from app.services.sante.pantry_fenetre import apply_pantry_deduction, load_pantry_grams


def test_load_pantry_grams_units():
    items = [{"ingredient": "Riz", "quantite": 1, "unite": "kg"},
             {"ingredient": "Oeufs", "quantite": 300, "unite": "g"},
             {"ingredient": "Riz", "quantite": 200, "unite": "g"}]
    g = load_pantry_grams(items)
    assert g["Riz"] == pytest.approx(1200.0)   # 1 kg + 200 g
    assert g["Oeufs"] == pytest.approx(300.0)


def test_deduction_partial_and_full():
    sl = [{"aliment": "Riz", "quantite_g": 900.0, "prix": 1.80, "promo": False},
          {"aliment": "Oeufs", "quantite_g": 200.0, "prix": 1.00, "promo": False}]
    out, cout = apply_pantry_deduction(sl, {"Riz": 200.0, "Oeufs": 500.0})
    riz = next(i for i in out if i["aliment"] == "Riz")
    assert riz["dispo_g"] == pytest.approx(200.0)
    assert riz["a_acheter_g"] == pytest.approx(700.0)
    assert riz["prix"] == pytest.approx(1.80 * 700 / 900)     # prorata
    assert all(i["aliment"] != "Oeufs" for i in out)          # tout en stock -> retiré
    assert cout == pytest.approx(1.80 * 700 / 900)
```

- [ ] **Step 2 — run RED** → FAIL (module absent).

- [ ] **Step 3 — implémentation**
```python
# backend/app/services/sante/pantry_fenetre.py
"""Garde-manger côté fenêtre : conversion en grammes + déduction quantité-limitée
de la liste de courses (spec §Phase 1). Pur, testable. NE touche pas au score
(le ratio reste sur le coût catalogue) — seule la partie À ACHETER change."""
from __future__ import annotations

_UNIT_G = {"g": 1.0, "kg": 1000.0, "mg": 0.001}


def load_pantry_grams(items: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for it in items:
        nom = (it.get("ingredient") or "").strip()
        if not nom:
            continue
        try:
            q = float(it.get("quantite") or 0)
        except (TypeError, ValueError):
            continue
        factor = _UNIT_G.get((it.get("unite") or "g").strip().lower(), 1.0)
        if q > 0:
            out[nom] = out.get(nom, 0.0) + q * factor
    return out


def apply_pantry_deduction(
    shopping_list: list[dict], pantry_g: dict[str, float]
) -> tuple[list[dict], float]:
    out: list[dict] = []
    cout_a_payer = 0.0
    for item in shopping_list:
        besoin = float(item.get("quantite_g") or 0.0)
        stock = float(pantry_g.get(item.get("aliment", ""), 0.0))
        dispo = min(besoin, stock)
        a_acheter = besoin - dispo
        if a_acheter <= 1e-9:
            continue  # tout en stock -> pas d'achat
        prix_total = float(item.get("prix") or 0.0)
        prix_achat = round(prix_total * (a_acheter / besoin), 2) if besoin > 0 else prix_total
        new = dict(item)
        new["dispo_g"] = round(dispo, 1)
        new["a_acheter_g"] = round(a_acheter, 1)
        new["prix"] = prix_achat
        cout_a_payer += prix_achat
        out.append(new)
    return out, round(cout_a_payer, 2)
```

- [ ] **Step 4 — run GREEN** → 2 passed.

- [ ] **Step 5 — commit** : `git commit -m "feat(sante): garde-manger fenetre - conversion grammes + deduction quantite-limitee"`

---

### Task 4 : câblage service + schémas

**Files:** Modify `backend/app/services/sante/fenetre_service.py`, `backend/app/api/sante/schemas.py` · Test `backend/tests/test_sante/test_fenetre_service.py` (ajout)

**Interfaces:** `ShoppingItem` gagne `dispo_g: float | None = None`, `a_acheter_g: float | None = None` ; `FenetreScore` gagne `cout_a_payer: float = 0.0`. `generate_window` charge le garde-manger, passe `pantry_names` à `optimize_ratio`, applique la déduction à `shopping_list`, écrit `cout_a_payer` dans `score`.

- [ ] **Step 1 — test (RED)** : ajouter à `test_fenetre_service.py` un test qui, avec un garde-manger monkeypatché (`{"Legume": 100000.0}` pour être sûr d'en avoir assez), vérifie que le `Legume` disparaît de `wp.shopping_list` (ou a `a_acheter_g < quantite_g`) et que `wp.score["cout_a_payer"] <= wp.score["cout_total"]`.
```python
def test_pantry_deducts_from_shopping_and_cout_a_payer(session, monkeypatch):
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "_load_pantry_items", lambda: [
        {"ingredient": "Legume", "quantite": 100, "unite": "kg"}])  # stock massif
    wp = fs.generate_window(session, day=dt.date(2026, 7, 20), poids=51.0)
    for it in wp.shopping_list:
        if it["aliment"] == "Legume":
            assert it["a_acheter_g"] < 100000  # déduit
    assert wp.score["cout_a_payer"] <= wp.score["cout_total"] + 1e-6
```

- [ ] **Step 2 — run RED** → FAIL.

- [ ] **Step 3 — implémentation**
  1. `schemas.py` : ajouter les champs (`ShoppingItem.dispo_g/a_acheter_g` optionnels ; `FenetreScore.cout_a_payer: float = 0.0`).
  2. `fenetre_service.py` :
     - Helper `_load_pantry_items()` (monkeypatchable) : `from app.services.cuisine import pantry; return pantry.list_items()` en best-effort (`except Exception: return []`).
     - Avant `optimize_ratio` : `pantry_g = load_pantry_grams(_load_pantry_items()); pantry_names = set(pantry_g)` et passer `pantry_names=pantry_names or None` à `optimize_ratio`.
     - Après `_build_shopping_list` : `shopping, cout_a_payer = apply_pantry_deduction(shopping, pantry_g)` (si `pantry_g`), sinon `cout_a_payer = score["cout_total"]`.
     - `score["cout_a_payer"] = cout_a_payer` avant de persister `wp.score`.
  3. `api/sante/fenetre.py::_to_response` : mapper `cout_a_payer` dans `FenetreScore` et `dispo_g/a_acheter_g` dans `ShoppingItem` (`ShoppingItem(**it)` les prendra si présents ; sinon défaut None).

- [ ] **Step 4 — run GREEN** : `pytest tests/test_sante/test_fenetre_service.py tests/test_sante/test_fenetre_api.py -q` → vert.

- [ ] **Step 5 — commit** : `git commit -m "feat(sante): fenetre applique le garde-manger (bonus optimiseur + deduction + cout a payer)"`

---

### Task 5 : frontend — affichage garde-manger dans l'onglet Fenêtre

**Files:** Modify `frontend/lib/sante.ts` (types), `frontend/components/sante/FenetreTab.tsx` · Test `frontend/__tests__/sante/fenetre-tab.test.tsx` (ajout)

**Interfaces:** `ShoppingItem` type += `dispo_g?: number|null; a_acheter_g?: number|null` ; `FenetreScore` type += `cout_a_payer: number`. FenetreTab : la liste affiche `dispo Xg` (barré/annoté) + `à acheter Yg`, et le bloc score montre **Coût à payer** à côté du coût (catalogue). L'ÉDITION du garde-manger réutilise l'écran cuisine existant (`GardeMangerTab`) — un lien/renvoi, pas de nouvel éditeur.

- [ ] **Step 1 — test (RED)** : dans `fenetre-tab.test.tsx`, ajouter un item avec `dispo_g: 200, a_acheter_g: 700` et `score.cout_a_payer: 30` → asserter que « à acheter » et le coût à payer s'affichent.
- [ ] **Step 2 — run RED**.
- [ ] **Step 3 — implémentation** : étendre les types dans `lib/sante.ts` ; dans FenetreTab, pour chaque item afficher `it.a_acheter_g != null ? \`${it.a_acheter_g.toFixed(0)} g à acheter${it.dispo_g ? ` (${it.dispo_g.toFixed(0)} g en stock)` : ""}\` : \`${it.quantite_g.toFixed(0)} g\`` ; dans le bloc score ajouter `Coût à payer <b>{win.score.cout_a_payer.toFixed(2)} $</b>` ; petite note « Édite ton garde-manger dans Cuisine ».
- [ ] **Step 4 — run GREEN** : `npx vitest run __tests__/sante/fenetre-tab.test.tsx` + `npx tsc --noEmit` + `npx eslint` (fichiers touchés) → vert.
- [ ] **Step 5 — commit** : `git commit -m "feat(sante-ui): affiche dispo/a acheter + cout a payer (garde-manger) dans l'onglet Fenetre"`

---

## PHASE 2 — Panier Super C (Instacart)

### Task 6 : matcher produit + cart plan (`cart_matcher.py`)

**Files:** Create `backend/app/services/sante/cart_matcher.py` · Test `backend/tests/test_sante/test_cart_matcher.py`

**Interfaces:**
- `best_product(cache_items, spec) -> dict | None` — le produit Instacart le MOINS cher (CAD/100 g comestible) matchant `spec` (réutilise `adonis_pricing._matches` + `adonis_price_per_100g_edible`), avec `id/href/format/price/name`.
- `cart_plan(shopping_list, cache_items, item_map=CATALOG_MAP) -> list[dict]` — pour chaque item **à acheter**, `{aliment, product_id, product_name, href, format, qty, prix_estime, a_verifier}` avec `qty = ceil(a_acheter_g / poids_du_format)` (format ml/L via densité≈1, comme le pricing) ; format absent → `qty=1, a_verifier=True` ; aliment non matché → `a_verifier=True`, sans product_id.

- [ ] **Step 1 — test (RED)**
```python
# backend/tests/test_sante/test_cart_matcher.py
from app.services.sante.cart_matcher import best_product, cart_plan

CACHE = [
    {"name": "Basmati Rice 1 kg", "id": "111", "href": "/products/111-rice-1-kg", "price": 4.69, "format": "1 kg"},
    {"name": "Basmati Rice 2 kg", "id": "222", "href": "/products/222-rice-2-kg", "price": 8.00, "format": "2 kg"},
]

def test_best_product_cheapest_per_100g():
    p = best_product(CACHE, {"kw": ["rice"], "edible": 1.0, "match": "any"})
    assert p["id"] == "222"   # 8/2kg = 0.40/100g < 4.69/1kg = 0.469/100g

def test_cart_plan_qty_ceil():
    sl = [{"aliment": "Riz", "a_acheter_g": 2500.0}]
    plan = cart_plan(sl, CACHE, item_map={"Riz": {"kw": ["rice"], "edible": 1.0, "match": "any"}})
    it = plan[0]
    assert it["product_id"] == "222" and it["format"] == "2 kg"
    assert it["qty"] == 2         # ceil(2500 / 2000)
    assert it["a_verifier"] is False

def test_cart_plan_unmatched_flagged():
    plan = cart_plan([{"aliment": "Licorne", "a_acheter_g": 100.0}], CACHE,
                     item_map={"Licorne": {"kw": ["unicorn"], "match": "any"}})
    assert plan[0]["a_verifier"] is True and plan[0].get("product_id") is None
```

- [ ] **Step 2 — run RED** → FAIL (module absent).

- [ ] **Step 3 — implémentation** : réutiliser `from app.services.sante.adonis_pricing import _matches, adonis_price_per_100g_edible, _format_weight_kg` ; `best_product` = min par `adonis_price_per_100g_edible` sur les items qui `_matches(spec)` ; `cart_plan` calcule `poids_format_g = _format_weight_kg(product)*1000` puis `qty = math.ceil(a_acheter_g / poids_format_g)` (≥1), `a_verifier` si pas de poids exploitable ou pas de match. `item_map` défaut = `CATALOG_MAP` (import de `superc_catalog_rebuild`).

- [ ] **Step 4 — run GREEN** → 3 passed.
- [ ] **Step 5 — commit** : `git commit -m "feat(sante): cart_matcher - produit Instacart chiffre + quantite paquets"`

---

### Task 7 : endpoint `GET /sante/fenetre/cart-plan`

**Files:** Modify `backend/app/api/sante/schemas.py`, `backend/app/api/sante/fenetre.py` · Test `backend/tests/test_sante/test_cart_plan_api.py`

**Interfaces:** `CartPlanItem` (aliment, product_id?, product_name?, href?, format?, qty, prix_estime?, a_verifier) + `CartPlanResponse {anchor_date, items: list[CartPlanItem], total_estime}`. `GET /sante/fenetre/cart-plan?date=` : charge la `WindowPlan` de l'ancre, rafraîchit le cache Super C (best-effort), lit `load_cached_items("superc")+("superc_flyer")`, appelle `cart_plan(wp.shopping_list, items)`.

- [ ] **Step 1 — test (RED)** : via `TestClient` (fixture StaticPool comme `test_fenetre_api.py`), générer une fenêtre, monkeypatcher les items cache Super C (factices avec id/format), puis `GET /sante/fenetre/cart-plan?date=2026-07-20` → 200, items non vides, chaque item a `qty>=1`.
- [ ] **Step 2 — run RED** → 404.
- [ ] **Step 3 — implémentation** : schémas + route ; charge cache via `store_pricing.load_cached_items` (best-effort), `get_current_window`, `cart_plan(...)`, mappe en `CartPlanResponse`. 404 si pas de fenêtre.
- [ ] **Step 4 — run GREEN**.
- [ ] **Step 5 — commit** : `git commit -m "feat(sante): endpoint /sante/fenetre/cart-plan (produits Instacart + quantites)"`

---

### Task 8 : frontend — section « Panier Super C »

**Files:** Modify `frontend/lib/sante.ts`, `frontend/lib/queries/sante.ts`, `frontend/components/sante/FenetreTab.tsx` · Test `frontend/__tests__/sante/cart-plan.test.tsx`

**Interfaces:** type `CartPlanResponse` + `santeApi.cartPlan(date?)` + hook `useCartPlan(date?)` ; section « Panier Super C » dans FenetreTab (tableau produit | format | qté | prix | lien | ⚠ à vérifier + total ; bouton « Préparer le panier »).

- [ ] **Step 1 — test (RED)** : mock `useCartPlan` → asserter que le nom produit, la qté et le badge « à vérifier » s'affichent.
- [ ] **Step 2 — run RED**.
- [ ] **Step 3 — implémentation** : client+hook (comme `fenetreCurrent`/`useFenetreCurrent`) ; section dans FenetreTab affichant `cartPlanQ.data.items`, chaque `href` en lien `https://www.instacart.ca${href}`, `a_verifier` → badge ⚠.
- [ ] **Step 4 — run GREEN** : vitest + tsc + eslint (fichiers touchés).
- [ ] **Step 5 — commit** : `git commit -m "feat(sante-ui): section Panier Super C (produits Instacart + quantites + liens)"`

---

### Task 9 : runbook remplissage live Claude-in-Chrome (doc, pas de code)

**Files:** Create `orchestration/finis/2026-07-23-runbook-remplissage-panier-superc.md`

**Interfaces:** N/A (procédure suivie par Claude avec les outils `mcp__claude-in-chrome__*`).

- [ ] **Step 1** : rédiger le runbook :
  1. Charger les outils Claude-in-Chrome (ToolSearch : tabs_context_mcp, navigate, computer, read_page, find, tabs_create_mcp).
  2. `tabs_context_mcp` → identifier/ouvrir un onglet `instacart.ca/store/super-c` (session du user).
  3. Récupérer le cart plan (`GET /sante/fenetre/cart-plan`).
  4. Pour chaque item avec `product_id` : `navigate` vers `https://www.instacart.ca/store/super-c/products/{product_id}`, régler la quantité (`qty`), cliquer **Add to cart** (via `find`/`computer`). Items `a_verifier` → montrer le lien au user, ne pas deviner.
  5. **Best-effort** : produit introuvable/indispo → sauter + noter. **Ne jamais** cliquer checkout/commander ; ne jamais vider le panier.
  6. Rapport final au user : ajoutés / sautés / à vérifier.
  7. Garde-fous : ne déclencher aucune boîte de dialogue (alert/confirm) ; en cas d'échec navigateur répété (2-3), s'arrêter et demander au user.
- [ ] **Step 2 — commit** : `git commit -m "docs(sante): runbook remplissage live du panier Super C (Claude-in-Chrome)"`

---

## Validation finale

- [ ] Backend : `./.venv/Scripts/python.exe -m pytest tests/test_sante tests/test_scheduler tests/test_migrations.py -q` → tout vert.
- [ ] Frontend : `npx vitest run __tests__/sante && npx tsc --noEmit` → vert.
- [ ] Revue finale inline : garde-fous respectés (bonus borné, ratio sur coût catalogue, cart-only) ; Minors triés.

## Séquencement

- Phase 1 (garde-manger, Tasks 1-5) **d'abord** — modifie A, livrable seul. Phase 2 (panier, Tasks 6-9) ensuite (dépend de la liste post-garde-manger).
- Exécution inline (subagents bloqués). Repasser subagent-driven si la limite de dépense est relevée.
