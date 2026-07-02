# Rattachement automatique pièce → type objectif (table de correspondance) — Design

**Date :** 2026-06-30
**Statut :** approuvé (design)

## Objectif

Éviter de rattacher à la main chaque vêtement à un type objectif. Une table de correspondance déterministe dérive `type_objectif` depuis la `sous_categorie` (fallback `categorie`) de la pièce. Déclenché par un bouton « Rattacher automatiquement » qui remplit les `type_objectif` **vides** uniquement.

## Décisions

- **Mécanisme : table de correspondance déterministe** (pas d'IA). Les vocabulaires `sous_categorie` et les 55 types objectif ne coïncident pas → mapping sémantique nécessaire (`Button Up → Chemises`, `Chelsea Boots → Bottines`, etc.). Une normalisation naïve ne couvre que 6/23.
- **Déclenchement : bouton seul** (pas d'auto à la création). Un endpoint bulk remplit les pièces non rattachées à la demande, re-jouable.
- **Jamais d'écrasement** : l'auto ne touche que `type_objectif is None`. Les choix manuels sont préservés.
- **Pièces non mappables** (montres, bijoux, lunettes de **vue** — absents des 55 types) → restent `None`, gérées par le sélecteur manuel existant.

## Backend

### Table + fonction pure
`backend/app/services/garderobe/objectif_mapping.py` :
- `MAPPING: dict[str, str]` — clé = libellé normalisé (`norm()` : NFKD→ASCII, minuscules, `[^a-z0-9]+`→espace, trim), valeur = nom **exact** d'un type objectif. Entrées connues (vocabulaire actuel) :
  - `t-shirt → T-shirts`, `t-shirt manches longues → T-shirts`, `polo → Polos`, `button up → Chemises`, `chemise → Chemises`, `chino → Pantalons chino`, `jean → Jeans`, `jean ballon → Jeans`, `wide-leg → Pantalons habillés`, `trackpants → Jogging`, `bomber → Vestes légères`, `veste sport → Vestes de sport`, `chelsea boots → Bottines`, `bottes de neige → Bottines`, `lunettes de soleil → Lunettes de soleil`.
  - (la table est complétable ; les clés sont normalisées à la lecture.)
- `norm(s: str | None) -> str` — normalisation partagée.
- `derive_type_objectif(categorie, sous_categorie, type_names: set[str] | list[str]) -> str | None` :
  1. cherche `norm(sous_categorie)` dans `MAPPING` ; sinon `norm(categorie)`.
  2. si trouvé ET la valeur ∈ `type_names` → renvoie la valeur ; sinon `None`.
  (Le contrôle d'appartenance aux 55 types évite d'écrire un type qui n'existe pas dans l'Excel courant.)

### Endpoint bulk
`POST /garderobe/objectif/auto-rattacher` (dans `app/api/garderobe/objectif.py`) :
- charge les noms de types (`ObjectifType.nom`) et tous les `Vetement` où `type_objectif is None`.
- pour chacun : `t = derive_type_objectif(v.categorie, v.sous_categorie, type_names)` ; si `t` → `v.type_objectif = t`.
- commit ; renvoie `{"rattaches": int, "non_mappes": int}` (non_mappes = pièces vides restées sans correspondance).

## Frontend

- `garderobeApi.autoRattacher()` → `POST /garderobe/objectif/auto-rattacher` ; hook `useAutoRattacher()` (mutation, invalide `["garderobe"]`).
- Onglet Objectif (`ObjectifTab.tsx`) : bouton « Rattacher automatiquement » à côté de « Re-synchroniser l'Excel ». Au clic : mutation, puis la vue se rafraîchit (emplacements remplis + compteur « non rattachées » à jour).

## Flux

1. L'utilisateur clique « Rattacher automatiquement ».
2. L'endpoint remplit les `type_objectif` vides depuis la table.
3. `invalidate(["garderobe"])` → l'onglet Objectif et l'Inventaire se rafraîchissent ; les pièces mappées remontent dans leur type.
4. Les pièces non mappables et les overrides restent gérés par le sélecteur manuel.

## Gestion d'erreur

- Échec du POST : mécanisme d'erreur global des mutations ; aucun changement partiel non commité (commit unique en fin).
- Pas de types chargés (objectif non synchronisé) : `type_names` vide → `derive_*` renvoie toujours `None` → `rattaches=0`, aucune écriture.

## Tests

- Backend purs (`derive_type_objectif`/`norm`) : mappings connus, pluriel/casse/accents, `sous_categorie` inconnue → `None`, valeur hors `type_names` → `None`, fallback `categorie`.
- Backend API : `auto-rattacher` remplit une pièce vide mappable, n'écrase pas une pièce déjà rattachée (manuelle), ignore une pièce non mappable (montre), renvoie les bons compteurs.
- Frontend : `useAutoRattacher` appelle l'API ; (léger) le bouton est présent dans l'onglet.

## Décomposition

1. Table + fonctions pures (`norm`, `derive_type_objectif`) + tests.
2. Endpoint `POST /objectif/auto-rattacher` + tests API.
3. Frontend : client + hook + bouton dans l'onglet ; exécution réelle (clic/endpoint) pour rattacher les 23 actuelles.

Sous-projet cohérent unique.
