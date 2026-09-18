# Repoint Super C : superc.ca au lieu d'Instacart (prix + promos + panier, en français)

Statut : à faire · Créé le 2026-07-23 · Supersède l'approche Instacart des prix Super C et du panier (sous-projet B)

## Contexte & déclencheur

Toute l'intégration Super C (prix de l'optimiseur nutrition + panier auto) a été bâtie sur
**Instacart** (`instacart.ca/store/super-c`). Deux problèmes soulevés par le user :

1. **Instacart majore les prix** (marge + frais de service/livraison) → le coût utilisé par
   l'optimiseur (donc le score couverture/coût et le budget) est **gonflé** vs. le vrai prix Super C.
2. Le matching se fait sur les **noms anglais** d'Instacart → faux matchs (`egg` matche `eggplant` :
   « Oeufs » → aubergine ; test live du 2026-07-23).

**Découverte (investigation navigateur 2026-07-23)** : `superc.ca` est désormais une **vraie
boutique en ligne** (plateforme e-commerce de Metro), pas seulement une circulaire :
- **Recherche catalogue** : `https://www.superc.ca/recherche?filter=<terme>` → catalogue complet,
  prix réels, badges **Promo**, noms **français** (« 552 produits pour riz »).
- **Carte produit (innerText)** ex. non-promo : `MINUTE RICE Riz blanc à grains longs précuit
  1,4 kg 6,99 $ ch. 0,50 $ /100g` ; promo : `Promo … 555 Riz basmati … 4,54 kg Prix régulier
  16,79 $ ch. 14,99 $ ch. 0,33 $ /100g`. → nom FR, **format**, **prix courant** (`$ ch.`),
  **prix/100 g direct** (`$ /100g`), **prix régulier** (promo), badge **Promo**.
- **URL produit stable** : `/allees/<catégories>/p/<CODE_UPC>` (ex. `/p/059100008027`) — le code
  est le **code-barres/UPC**, idéal pour matcher et re-trouver un produit.
- **Panier propre** : boutons « Ajouter au panier » sur chaque carte + `/mon-panier` ; le user est
  **déjà connecté** (panier à 5 articles). Bascule FR/EN.
- **« Commandité »** = produit sponsorisé (à ignorer au scrape).

Conclusion : on peut **tout faire sur superc.ca** — prix + promos + remplir le panier — aux
**vrais prix Super C**, sur le **compte du user**, en **français**. Instacart devient obsolète.

## Décisions validées avec le user (2026-07-23)

1. **Repoint complet** vers superc.ca (prix + promos + panier), en **français**.
2. **Prix réguliers** : scraper `superc.ca/recherche?filter=<terme>` (au lieu d'`instacart.ca`).
3. **Matching en français** : les noms d'aliments du catalogue sont déjà FR → matcher sur le FR
   (fin des faux matchs anglais).
4. **Panier** : remplir sur superc.ca (`/p/<UPC>` + « Ajouter au panier »), **cart-only, ajout
   seul, jamais de checkout**.
5. **Instacart** : déprécié comme source de prix et de panier.

## Repoint — pièces à modifier

### A. Scraper prix `frontend/.superc_scrape.mjs`
- Réécrire pour naviguer `https://www.superc.ca/recherche?filter=<terme>` (par terme de recherche,
  comme aujourd'hui) et extraire chaque carte produit via `page.evaluate` :
  - `name` (FR), `format` (« 1,4 kg »), `price` (courant = `X,XX $ ch.` ; pour une promo, le prix
    **soldé**), `unit_price_100g` (`X,XX $ /100g` — **direct**), `regular_price` (`Prix régulier`),
    `on_sale` (badge **Promo**), `code`/`sku` (UPC depuis `/p/<code>`), `href` (`/allees/.../p/<code>`).
  - **Ignorer** les cartes « Commandité ».
- **Schéma de sortie `superc.json`** : garder les clés existantes consommées ailleurs
  (`name, id, href, price, unit_price, unit, original_price, on_sale, format`) + ajouter
  `sku` (UPC) et `price_per_100g` (depuis `$ /100g`). `id` = UPC. `href` = chemin superc.ca.
- Best-effort inchangé (0 item → cache conservé, jamais d'écrasement destructeur).
- Le sélecteur DOM exact des cartes est à établir en écrivant le scraper (charger la page réelle,
  inspecter) ; l'ancre fiable = les liens `a[href*="/allees/"][href*="/p/"]` (un par produit) et le
  texte de la carte parente contient nom/format/prix/`$ /100g`/Promo.

### B. Matching en français (`superc_catalog_rebuild.py` `CATALOG_MAP` + `adonis_pricing.py`)
- Le matching mots-clés (`_matches`, `build_price_overlay`, `CATALOG_MAP`, `PRODUCE_MAP`) passe
  aux **mots-clés français**. Comme chaque aliment du catalogue a un **nom FR** (« Oeufs »,
  « Riz blanc », « Brocoli »…), le nom lui-même est un bon mot-clé ; ajouter synonymes FR + `not`
  FR (ex. Oeufs : `kw:["oeuf","œuf"]`, `not:["aubergine"]`). Réviser les ~120 entrées contre le
  vrai `superc.json` FR.
- **Prix/100 g direct** : quand la carte fournit `price_per_100g`, l'utiliser directement (plus
  besoin de dériver via format×poids) ; garder la dérivation format comme repli.

### C. Overlay prix optimiseur (`adonis_pricing.py` / `superc_catalog_rebuild.py`)
- `catalog_price_overlay` / `build_price_overlay` consomment le nouveau `superc.json` FR : prix =
  `price_per_100g` si présent, sinon dérivé. Les fonctions restent (le nom « adonis » est hérité).

### D. Panier `cart_matcher.py` + endpoint + runbook
- `cart_matcher` : le produit retourné porte le `code`/UPC + le `href` superc.ca. Quantité :
  `ceil(a_acheter_g / poids_format)` inchangé (le format vient toujours de la carte).
- `runbook-remplissage-panier-superc.md` : cible **superc.ca** — naviguer `superc.ca<href>` (ou
  `/produit/<code>`), cliquer **« Ajouter au panier »**, sur le **compte du user** (déjà connecté),
  **cart-only, ajout seul, jamais de checkout**. Retirer les étapes Instacart.

### E. Circulaire (`.superc_flyer_scrape.mjs`)
- **Inchangée** (déjà `circulaire.superc.ca`). Optionnel : les promos sont aussi sur `/recherche`
  (badges) — on peut à terme fusionner, mais hors scope ici.

### F. Dépréciation Instacart
- L'ancien scrape `instacart.ca` et les mentions « Instacart » (docstrings, runbook) sont retirés
  ou marqués obsolètes. Pas de suppression agressive de code réutilisé (matching pur).

## Hors scope
- Passer la commande / créneaux / paiement (toujours cart-only).
- Login automatique (on s'appuie sur la session superc.ca du user).
- Refonte de la circulaire (reste sur son API Metro).
- Optimisation multi-magasins.

## Risques assumés
- **DOM superc.ca peut changer** → scraper best-effort, cache conservé sur échec.
- **Matching FR imparfait** sur ~120 items → révision contre le vrai `superc.json` + drapeau
  `a_verifier` côté panier + revue avant remplissage.
- **superc.ca peut aussi avoir des frais** (livraison) au checkout — mais les **prix articles**
  sont les vrais prix Super C (pas la marge Instacart) ; le cueillette évite les frais de livraison.
- Le store online (6160 De Lorimier) diffère du store circulaire (847 St-Jacques) — cohérence de
  magasin à surveiller.

## Critères d'acceptation
- `superc.json` reconstruit depuis superc.ca : noms FR, `price_per_100g` réels, UPC, promos.
- Matching FR : « Oeufs » → un produit d'œufs (jamais aubergine) ; « Riz blanc » → un riz.
- Overlay optimiseur : prix = vrais prix Super C (visiblement < Instacart sur un échantillon).
- Panier : cart_plan pointe des `/p/<UPC>` superc.ca ; runbook cible superc.ca.
- Tests backend verts (matching/overlay/cart adaptés) + garde-fous best-effort.
