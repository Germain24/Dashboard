# Garde-manger + panier Super C (Instacart) — sous-projet B

Statut : à faire · Créé le 2026-07-23 · Fait suite au sous-projet A (fenêtre nutrition, livré)

## Contexte

Le sous-projet A est livré : entrer son poids (lun/jeu) génère un plan fenêtre (3/4 j),
une **liste de courses agrégée à cocher** (`WindowPlan.shopping_list`) et un score
couverture-micro/coût. Deux ajouts demandés maintenant :

1. **Garde-manger** — le user veut déclarer ce qu'il a déjà en stock (gratuit à l'achat, déjà
   payé) pour ne pas le racheter, et pour que l'optimiseur **penche vers ce qu'il a**.
2. **Panier Super C automatique** — remplir le panier Instacart réel à partir de la liste de
   courses (c'était le « plus tard » du plan A).

Matière première déjà en place :
- **Super C = Instacart** ; cache `data/imports/Cuisine/superc.json` (~717 produits) avec, par
  produit : `id` Instacart, `href` (`/products/{id}-slug`), `format` (« 1 kg », « 150 g »…),
  `price`, `unit_price`/`unit`, `on_sale`. Scrapers **lecture seule** (recherche → extraction),
  rafraîchis best-effort.
- **Matching mots-clés** aliment→produit déjà utilisé pour les prix
  (`build_price_overlay` / `catalog_price_overlay`, `app/services/sante/superc_catalog_rebuild.py`
  + `adonis_pricing.py`) : il choisit le produit Instacart le moins cher par aliment.
- **Infra garde-manger** côté cuisine : `data/cuisine_pantry.json`, service
  `app/services/cuisine/pantry.py` (`list_items()`), et déduction
  `app/services/cuisine/shopping_list.py` (`pantry_to_inventaire`, `apply_inventaire`).
- **Claude-in-Chrome** : outils `mcp__claude-in-chrome__*` disponibles (pilotage du Chrome du
  user, sur sa session Instacart connectée).

## Décisions validées avec le user (2026-07-23)

1. **Mécanisme panier = Claude-in-Chrome en live** : Claude pilote le Chrome du user (session
   Instacart déjà connectée) et ajoute chaque produit ; pas de gestion de mot de passe, pas de
   script headless avec login sauvegardé.
2. **Cart-only, JAMAIS de commande passée** ; **ajout seul** (ne vide/modifie jamais le panier
   existant) ; **revue avant remplissage**.
3. **Garde-manger** : il doit **prioriser le stock MAIS jamais produire un repas déséquilibré**
   sous prétexte que c'est gratuit. Résolu structurellement (cf. Phase 1).
4. **Garde-fou score** : le coût du **ratio** reste ≠ 0 (prix catalogue pour tous les aliments) →
   pas de dérive « n'achète rien / ratio infini ». Le garde-manger ne réduit que le **coût à
   payer** (out-of-pocket) et la liste de courses.
5. **Séquencement** : Phase 1 (garde-manger) d'abord — livrable seul, modifie A —, puis Phase 2
   (panier).

---

## Phase 1 — Garde-manger

### Principe : l'équilibre est déjà non-négociable

La crainte « il mange que le stock gratuit et fait un repas déséquilibré » est **structurellement
impossible** avec l'optimiseur actuel, car l'équilibre est imposé **indépendamment du coût** :
calories & protéines = **contraintes dures** (≥ cible) ; lipides/glucides visés + plafonds
sodium/sucre/gras saturés ; micros = numérateur du score. Le stock ne peut donc que **pencher le
choix**, pas déséquilibrer.

### Mécanique

1. **Données** : réutiliser `cuisine_pantry.json` via `cuisine/pantry.py`. Le garde-manger =
   `{aliment: quantité_en_stock_g}` (les noms d'aliments doivent matcher le catalogue). Un
   mapping/normalisation garde-manger→noms catalogue est fourni si les libellés diffèrent.
2. **Priorité au stock = bonus borné dans l'optimiseur** : `optimize_nutrition` reçoit un
   ensemble d'aliments « en stock » et applique un **petit terme de préférence** (même échelle que
   le terme `taste_arr`/diversité existant) qui récompense l'usage du stock. Il est **assez petit
   pour ne jamais l'emporter sur les macros (100–1000) ni la couverture (60)** → équilibre garanti,
   priorité au stock seulement à valeur nutritionnelle comparable.
3. **Coût du ratio inchangé** : le dénominateur du score = **prix catalogue** de TOUS les aliments
   (garde-manger inclus) → ≠ 0, jamais dégénéré. Passe par le ratio_optimizer tel quel.
4. **Déduction quantité-limitée (post-optimisation)** : la `shopping_list` de la `WindowPlan` et
   le **coût à payer affiché** déduisent le stock : pour chaque aliment, `à_acheter_g =
   max(0, besoin_g − stock_g)` ; prix à payer = prix du seul `à_acheter_g`. Réutilise la logique
   `apply_inventaire`. Le **score/ratio reste calculé sur le plan complet** (Phase 1 ne touche pas
   au score) ; on ajoute juste un **coût out-of-pocket** informatif à la réponse.

### Sortie / modèle

- `WindowPlan.shopping_list` : chaque item gagne `dispo_g` (stock déduit) et `a_acheter_g` ;
  `prix` devient le prix du `a_acheter_g`. Un champ `cout_a_payer` (somme) s'ajoute au `score`
  (distinct de `cout_total`, qui reste le coût catalogue du plan pilotant le ratio).
- Rien ne change au `WindowPlan.food_set` ni aux `PlanNutrition`/jour (le plan mangé est le même ;
  seule la partie à ACHETER change).

### UX

- Onglet Fenêtre : petit éditeur **« Garde-manger »** (ajouter/retirer aliment + quantité), ou
  bouton vers l'écran garde-manger cuisine existant. La liste de courses affiche `dispo Xg` barré
  et le `à acheter`, plus le **coût à payer** à côté du coût catalogue.

### Tests (acceptation)

- Bonus stock : à deux aliments nutritionnellement équivalents, l'optimiseur choisit celui en
  stock ; mais si le stock ne suffit pas aux macros, il achète le complément (équilibre préservé).
- Le bonus ne dégrade pas l'atteinte des macros/couverture au-delà d'un seuil (test comparant
  couverture avec/sans bonus sur catalogue factice).
- Déduction : besoin 900 g, stock 200 g → `a_acheter_g = 700`, `cout_a_payer` = prix de 700 g ;
  stock ≥ besoin → item retiré de la liste, `cout_a_payer = 0` pour cet item.
- Score/ratio inchangé par le garde-manger (dénominateur = coût catalogue plein).

---

## Phase 2 — Panier Super C (Instacart) via Claude-in-Chrome

### Brique matching (backend, pure & testable)

- `cart_plan(shopping_list)` : pour chaque item **à acheter** (post-garde-manger), réutiliser le
  matching mots-clés existant pour retrouver **le même produit Instacart que l'optimiseur a
  chiffré** → extraire `product_id`, `product_name`, `href`, `format`, `prix`.
- **Quantité** : `qty = ceil(a_acheter_g / poids_du_format)` (ex. 700 g riz, format « 1 kg » →
  1). Produit au poids/à l'unité sans format exploitable → `qty = 1` + `a_verifier = true`.
- Sortie = **cart plan** :
  `[{aliment, product_id, product_name, href, format, qty, prix_estime, a_verifier}]`.
- Exposé via `GET /sante/fenetre/cart-plan` (dérivé de la `WindowPlan` courante ; rafraîchit le
  cache Super C avant, comme pour les prix).

### Brique remplissage live (Claude-in-Chrome, à la demande)

Procédure documentée (petit runbook/skill), suivie par Claude avec les outils navigateur — **pas
un service autonome** :
1. `tabs_context` → onglet `instacart.ca/store/super-c` (session du user).
2. Pour chaque item du cart plan : aller sur `/products/{product_id}`, régler la quantité `qty`,
   cliquer **Ajouter au panier**.
3. **Best-effort par item** : produit introuvable/indisponible → **sauté + rapporté**, jamais
   bloquant. Aucune boîte de dialogue déclenchée (contrainte Claude-in-Chrome).
4. **Rapport final** : ajoutés / sautés / à vérifier. **Jamais de checkout.** Ne vide/modifie
   jamais le panier existant.

### UX

- Onglet Fenêtre, section **« Panier Super C »** sous la liste de courses : tableau
  `produit Instacart | format | qté | prix | lien | ⚠ à vérifier` + total. Bouton **« Préparer le
  panier »** (prépare/affiche le cart plan) ; le remplissage réel se fait quand le user demande à
  Claude (mécanisme live).

### Tests (acceptation)

- Matching : sur un `superc.json` factice, un aliment donné → le bon `product_id`/`href`/`format`
  attendu ; aliment sans match → absent du cart plan (ou `a_verifier`).
- Quantité : `ceil(besoin/format)` correct ; format ml/L converti (densité ≈ 1, comme le pricing) ;
  format absent → `qty=1`, `a_verifier=true`.
- Endpoint `cart-plan` : renvoie une entrée par item à acheter, cohérente avec la `shopping_list`
  post-garde-manger.
- Le remplissage live n'est pas testé automatiquement (dépend du navigateur/session) : couvert par
  le runbook + best-effort.

## Hors scope (B)

- Passer la commande / créneaux de livraison / paiement.
- Login Instacart automatisé, script headless avec session sauvegardée (on s'appuie sur la session
  Chrome du user).
- Plusieurs magasins.
- Score recalculé sur le coût out-of-pocket (le ratio reste sur le coût catalogue — décision user).

## Risques assumés

- Matching cache↔produit imparfait → **revue** dans l'UI + drapeau `a_verifier` + ajout best-effort.
- UI Instacart peut changer et casser le clic « Ajouter » → best-effort, signalé dans le rapport.
- Cache `superc.json` périmé → produit indisponible → rafraîchi avant, sauté sinon.
- Bonus garde-manger mal calibré → réglé petit (sous les poids macro/couverture) + test de
  non-régression d'équilibre.
