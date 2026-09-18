# Repoint Super C → superc.ca — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. Le contrôleur peut exécuter le scraper (Task 1) lui-même s'il a un accès navigateur ; les tâches Python/doc sont déléguables aux subagents.

**Goal:** Repointer toute l'intégration Super C (prix optimiseur + panier) d'Instacart vers **superc.ca** — vrais prix, noms **français**, code UPC — ce qui corrige la majoration Instacart ET les faux matchs anglais (œufs→eggplant).

**Architecture:** Le scraper produit un `superc.json` FR (nom, `price_per_100g` direct, UPC, promo). Le matching passe en français (les noms d'aliments du catalogue sont déjà FR). L'overlay prix et `cart_matcher` consomment ce schéma. Le runbook panier cible superc.ca (compte du user, cart-only).

**Tech Stack:** node + playwright-core + Edge (scraper) ; Python/FastAPI (matching, overlay, cart) ; Claude-in-Chrome (remplissage).

## Global Constraints
- Spec : `orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md`.
- Branche active `chore/audit-quick-wins`, pas d'isolation.
- Tests backend : `./.venv/Scripts/python.exe -m pytest ...` depuis `backend/` ; ruff via `--config ruff-ci.toml`.
- Commits FR + trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Best-effort scrape** : 0 item → cache conservé (jamais d'écrasement). **Cart-only** : jamais de checkout.
- Schéma `superc.json` (contrat entre Task 1 et 2-4) — chaque item :
  `{ name(FR), id(UPC), sku(UPC), href("/allees/.../p/<UPC>"), price(courant $), price_per_100g(float|null), unit_price, unit, original_price(régulier, promo), on_sale(bool), format }`.

---

### Task 1 : Réécrire le scraper prix pour superc.ca (`frontend/.superc_scrape.mjs`)

**Files:** Rewrite `frontend/.superc_scrape.mjs`.

**Contexte carte produit** (innerText réel observé sur `superc.ca/recherche?filter=riz`) :
- Non-promo : `MINUTE RICE Riz blanc à grains longs précuit 1,4 kg 6,99 $ ch. 0,50 $ /100g`
- Promo : `Promo … 555 Riz basmati, Format économique 4,54 kg Prix régulier 16,79 $ ch. 14,99 $ ch. 0,33 $ /100g`
- Sponsorisé : contient `Commandité` → **ignorer**.
- Ancre fiable : un lien `a[href*="/allees/"][href*="/p/<UPC>"]` par produit ; la carte parente (remonter jusqu'au 1er ancêtre dont l'innerText contient `$`) porte nom/format/prix/`$ /100g`/Promo.

**Steps:**
- [ ] **1.** Écrire le scraper : `node .superc_scrape.mjs <sortie.json> <terme1> <terme2> …`, headless Edge (même launch que l'ancien / que `.superc_flyer_scrape.mjs`), pour chaque terme `page.goto('https://www.superc.ca/recherche?filter=' + encodeURIComponent(terme))`, `page.evaluate` extrait par carte : `name` (nom FR, sans « Ajouter à vos favoris »/« Promo »/« Commandité »/« Produit du … »/format/prix), `format`, `price` (courant = dernier `X,XX $ ch.` ; promo = prix soldé), `price_per_100g` (depuis `X,XX $ /100g`), `original_price` (`Prix régulier X,XX`), `on_sale` (a « Promo »), `id`/`sku` = UPC (`/p/(\w+)`), `href`. Dédupliquer par UPC. Ignorer `Commandité`.
- [ ] **2.** Repli best-effort : 0 item ET cache existant non vide → ne pas écraser (comme l'ancien). Écrire `{source:'superc.ca/recherche', scraped_at, count, items}`.
- [ ] **3.** Tester réellement : `cd frontend && node .superc_scrape.mjs ../data/imports/Cuisine/superc.test.json riz oeufs brocoli banane` → vérifier que le JSON a des **noms FR**, des `price_per_100g` numériques, des UPC, et des `on_sale` sur les promos. Comparer 2-3 prix à Instacart (doivent être ≤). Supprimer le fichier test après.
- [ ] **4.** Commit : `git commit -m "feat(cuisine): scraper prix Super C sur superc.ca (noms FR, prix reels, UPC, $/100g)"`.

> Note contrôleur : cette tâche lance un vrai navigateur headless (node/Playwright/Edge). Un subagent peut l'exécuter (il n'a pas besoin du MCP navigateur, Playwright lance son propre Edge) ; sinon le contrôleur la fait.

---

### Task 2 : Overlay prix depuis le nouveau schéma (`adonis_pricing.py`)

**Files:** Modify `backend/app/services/sante/adonis_pricing.py` · Test `backend/tests/test_sante/test_superc_price_per_100g.py`

**Steps:**
- [ ] **1.** Test (RED) : `adonis_price_per_100g_edible(item, edible)` — quand `item["price_per_100g"]` est présent (float), le retourner (divisé par edible), sans dériver via format. Fixture item `{price_per_100g: 0.50, ...}` edible 1.0 → 0.50 ; edible 0.9 → 0.556.
- [ ] **2.** RED : `pytest tests/test_sante/test_superc_price_per_100g.py`.
- [ ] **3.** Implémenter : en tête de `adonis_price_per_100g_edible`, `pp = item.get("price_per_100g")` ; si `pp` numérique > 0 → `return round(float(pp)/ (edible or 1.0), 3)`. Sinon logique existante (unit_price / format) inchangée (repli).
- [ ] **4.** GREEN + `pytest tests/test_sante -q` (aucune régression) + ruff-ci.
- [ ] **5.** Commit `feat(sante): overlay prix utilise price_per_100g direct de superc.ca`.

---

### Task 3 : Matching en français (`superc_catalog_rebuild.py` + `adonis_pricing.py`)

**Files:** Modify `backend/app/services/sante/superc_catalog_rebuild.py` (`CATALOG_MAP`, `_DAIRY_EGGS_SPEC`), `backend/app/services/sante/adonis_pricing.py` (`PRODUCE_MAP`) ; `backend/app/services/cuisine/store_categories.py` (`NON_PRODUCE_KW`) si c'est la source des mots-clés · Test `backend/tests/test_sante/test_matching_fr.py`

**Steps:**
- [ ] **1.** Test (RED) : sur un `superc.json` factice FR (`[{name:"MINUTE RICE Riz blanc à grains longs", ...}, {name:"Aubergine …"}, {name:"Oeufs gros …"}, {name:"Brocoli …"}]`), `build_price_overlay`/`best_product` : « Oeufs » → l'item œufs (jamais l'aubergine) ; « Riz blanc » → le riz ; « Brocoli » → le brocoli.
- [ ] **2.** RED.
- [ ] **3.** Passer les mots-clés en **français** : chaque spec `kw` en FR (le nom d'aliment FR est un bon mot-clé), `not` en FR (Oeufs : `kw:["oeuf","œuf"]`, `not:["aubergine"]` ; etc.). Réviser les ~120 entrées de `CATALOG_MAP`/`PRODUCE_MAP`/`_DAIRY_EGGS_SPEC`. `_matches` reste inchangé (il matche déjà `name`+`href`, désormais FR).
- [ ] **4.** GREEN + validation contre le **vrai** `superc.json` FR (Task 1) : script ad hoc listant, pour chaque aliment du catalogue, le produit matché — repérer les faux matchs restants, corriger. Journaliser dans le rapport.
- [ ] **5.** `pytest tests/test_sante -q` + ruff-ci. Commit `feat(sante): matching produits Super C en francais (fin des faux matchs anglais)`.

---

### Task 4 : `cart_matcher` sur schéma superc.ca (`cart_matcher.py`)

**Files:** Modify `backend/app/services/sante/cart_matcher.py` · Test `backend/tests/test_sante/test_cart_matcher.py` (adapter)

**Steps:**
- [ ] **1.** Adapter les tests : le `CACHE` factice utilise le schéma superc.ca (`name` FR, `id`=UPC, `href`="/allees/.../p/<UPC>", `format`, `price`, `price_per_100g`). Asserts : `best_product` prend le moins cher au 100 g (via `price_per_100g` si présent) ; `cart_plan` renvoie `product_id`=UPC + `href` superc.ca + `qty=ceil(a_acheter/format)`.
- [ ] **2.** RED/GREEN : le code `cart_matcher` change peu (il consomme déjà `_matches`/`adonis_price_per_100g_edible`/`_format_weight_kg`) — surtout vérifier que `href`/`id` UPC passent. Ajuster si besoin.
- [ ] **3.** `pytest tests/test_sante/test_cart_matcher.py tests/test_sante/test_cart_plan_api.py -q` + ruff-ci. Commit `feat(sante): cart_matcher sur produits superc.ca (UPC + href)`.

---

### Task 5 : Runbook panier → superc.ca

**Files:** Modify `orchestration/runbook-remplissage-panier-superc.md`

**Steps:**
- [ ] **1.** Repointer le runbook : ouvrir/réutiliser un onglet `superc.ca` (session du user, déjà connecté) ; pour chaque item, `navigate` vers `https://www.superc.ca<href>` (ou `/recherche?filter=<nom>` puis la bonne carte), cliquer **« Ajouter au panier »** ; items `a_verifier` → montrer au user. **Cart-only, ajout seul, jamais de checkout** ; ne pas toucher aux 5 articles existants. Retirer les étapes Instacart.
- [ ] **2.** Commit `docs(sante): runbook panier cible superc.ca (au lieu d'Instacart)`.

---

### Task 6 : Déprécier les mentions Instacart

**Files:** `frontend/.superc_scrape.mjs` (fait en T1), docstrings de `adonis_pricing.py` / `store_pricing.py` / commentaires ; éventuel `.adonis_scrape.mjs` si mort.

**Steps:**
- [ ] **1.** Grep `instacart` / `Instacart` dans `backend/app` + `frontend/*.mjs` ; corriger les docstrings/commentaires devenus faux (source = superc.ca). Ne pas casser de code réutilisé.
- [ ] **2.** `pytest tests/test_sante tests/test_cuisine -q` + ruff-ci. Commit `chore(sante): deprecation des mentions Instacart (source = superc.ca)`.

---

## Validation finale
- [ ] `superc.json` réel reconstruit (Task 1) : FR, `price_per_100g`, UPC, promos.
- [ ] Matching FR validé contre le vrai cache (Oeufs≠aubergine, Riz blanc→riz).
- [ ] `pytest tests/test_sante tests/test_cuisine tests/test_scheduler tests/test_migrations.py -q` vert.
- [ ] Revue finale + essai panier live sur superc.ca (user connecté).

## Séquencement
- Task 1 (scraper) d'abord (fournit le schéma + les données). Tasks 2-4 en parallèle possible sur fixtures, validées ensuite contre le vrai cache. Tasks 5-6 après.
- Subagent-driven (limite de dépense relevée par le user 2026-07-23).
