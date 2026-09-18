# Runbook — remplir le panier Super C (superc.ca) via Claude-in-Chrome

Procédure que **Claude** suit, à la demande de l'utilisateur (« remplis le panier Super C »),
pour ajouter les produits de la fenêtre nutrition au **panier superc.ca** (la vraie boutique en
ligne Metro/Super C, aux vrais prix — pas Instacart). **Cart-only : jamais de checkout, jamais de
commande, ajout seul (on ne vide/modifie pas le panier existant de l'utilisateur).**

Réf : `orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md` (§D).

## Pré-requis
- L'utilisateur est **connecté à superc.ca** dans son Chrome (magasin sélectionné = son Super C,
  ex. De Lorimier / H2X 0B4 ; il a déjà un panier). On n'entre jamais ses identifiants.
- Une **fenêtre nutrition existe** (onglet Santé → Fenêtre).

## Étapes

1. **Charger les outils Claude-in-Chrome** en un seul ToolSearch :
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find,mcp__claude-in-chrome__tabs_create_mcp`

2. **Récupérer le cart plan** : `GET /sante/fenetre/cart-plan` (fenêtre courante). Chaque item :
   `{aliment, product_id (UPC), product_name, href ("/allees/.../p/<UPC>"), format, qty, prix_estime, a_verifier}`.

3. **Contexte des onglets** : `tabs_context_mcp`. Réutiliser un onglet `superc.ca` connecté (session
   du user, hors challenge Cloudflare car navigation humaine) ; sinon `tabs_create_mcp` puis
   `navigate` vers `https://www.superc.ca/` et vérifier que le bon magasin est sélectionné + le user
   connecté (panier non vide, « Se connecter » absent). Si non connecté → **s'arrêter et demander au
   user de se connecter** (on ne se connecte jamais à sa place).

4. **Pour chaque item avec `product_id` et `a_verifier = false`** :
   - `navigate` vers `https://www.superc.ca<href>` (la fiche produit `/allees/.../p/<UPC>`).
   - Régler la quantité sur `qty`, puis cliquer **« Ajouter au panier »** via `find` (« Ajouter au
     panier ») + `computer`.
   - Vérifier (`read_page` / screenshot) que le compteur du panier a augmenté.
   - Repli si la fiche ne charge pas : `navigate` vers `https://www.superc.ca/recherche?filter=<nom>`
     et cliquer « Ajouter au panier » sur la carte dont l'UPC (lien `/p/<UPC>`) correspond.

5. **Items `a_verifier = true`** (produit non chiffrable ou aliment non matché) : **ne pas deviner**.
   Montrer le lien/nom au user et le laisser choisir.

6. **Best-effort** : produit introuvable/indisponible/UI changée → **sauter** + noter. Après 2-3
   échecs navigateur consécutifs, **s'arrêter** et demander au user.

7. **Garde-fous** :
   - **Jamais** « Passer à la caisse » / « Commander » / checkout.
   - **Ne pas** vider ni réduire le panier existant du user (ajout uniquement).
   - **Ne déclencher aucune boîte de dialogue** (alert/confirm) — cela bloque l'extension.

8. **Rapport final** : **ajoutés** (produit × qty), **sautés** (raison), **à vérifier** (avec liens).
   Rappeler que le user **revoit puis checkoute lui-même** (superc.ca peut ajouter des frais de
   livraison au checkout ; la cueillette les évite — mais les **prix articles** sont les vrais prix
   Super C, pas la marge Instacart).

## Notes
- Le matching aliment→produit vient du cache `superc.json` (**superc.ca**, noms FR, UPC) — les mêmes
  produits que ceux chiffrés par l'optimiseur. Cache périmé → produit indisponible → sauté + signalé.
- Procédure **interactive** pilotée par Claude sur le navigateur du user, **pas** un service autonome.
- **Historique** : ce runbook ciblait Instacart (`instacart.ca/store/super-c`) jusqu'au 2026-07-23 ;
  repointé vers superc.ca (vrais prix, compte du user, français) — cf. la spec de repoint.
