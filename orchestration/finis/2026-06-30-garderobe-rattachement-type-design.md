# Rattachement pièce → type objectif — Design

**Date :** 2026-06-30
**Statut :** approuvé (design)

## Objectif

Permettre de rattacher chaque vêtement de la garde-robe à l'un des 55 types objectif (T-shirts, Polos…), pour que l'onglet « Objectif » se remplisse (un emplacement par pièce rattachée, positionné à la marque sur l'échelle Q/P→Max). Sans cette UI, `Vetement.type_objectif` ne peut être défini que par appel API direct, donc `total_remplis` reste à 0.

## Périmètre

**Frontend uniquement.** Le backend supporte déjà tout :
- `PATCH /garderobe/vetements/{id}` accepte `type_objectif` (str | null) — via `VetementUpdate` + `model_dump(exclude_unset=True)`.
- `GET /garderobe/objectif` renvoie déjà `types[].nom` (les 55 noms).

Aucun changement API/DB/schéma. Aucun nouvel endpoint.

**Hors scope :** bulk-assign, section de rattachement dans l'onglet Objectif (l'utilisateur a choisi le sélecteur Inventaire seul), logos, combinatoire, BonneGueule.

## Décision : emplacement

Le rattachement se fait via un **sélecteur sur chaque carte de l'onglet Inventaire** (option retenue parmi : carte Inventaire / section dans Objectif / les deux).

## Décision : source des options

Réutiliser le hook **`useObjectif()`** existant (sa réponse contient `types[].nom`). React Query cache sous `["garderobe","objectif"]`, partagé entre onglets. Pas de nouvel endpoint (YAGNI). Si la donnée n'est pas encore chargée, le select s'affiche désactivé/vide jusqu'à l'arrivée des types.

## Composants

### `InventaireTab.tsx`
- Appelle `useObjectif()`, extrait `typeNames = (objectifQ.data?.types ?? []).map(t => t.nom)`.
- Passe `typeNames` à chaque `VetementCard`.

### `VetementCard`
- Nouveau `<select>` « Type objectif » en bas de carte :
  - options : une option vide `— Type objectif —` (value `""`) + un `<option>` par nom de `typeNames`.
  - `value = v.type_objectif ?? ""`.
  - `onChange` → `useUpdateVetement().mutate({ id: v.id, patch: { type_objectif: value || null } })`. L'option vide envoie `null` (déliaison).
- Si `v.type_objectif` est défini mais absent de `typeNames` (cas orphelin pré-existant), l'afficher quand même comme option sélectionnée (ne pas perdre la valeur affichée).
- Style cohérent avec les filtres existants (`var(--border)`, `var(--card)`, classes `text-xs`/`rounded`).
- `useUpdateVetement` existe déjà (`lib/queries/garderobe.ts`) et invalide `["garderobe"]` → l'onglet Objectif (et son compteur « non rattachées ») se met à jour automatiquement.

## Flux de données

1. L'utilisateur ouvre Inventaire → `useObjectif()` fournit les noms de types (cache partagé).
2. Il choisit un type dans le select d'une carte → `PATCH /vetements/{id}` `{type_objectif}`.
3. `onSuccess` invalide `["garderobe"]` → `useVetements` et `useObjectif` se re-fetchent → la carte montre la nouvelle valeur, l'onglet Objectif montre l'emplacement rempli.
4. Choix de l'option vide → `type_objectif: null` → la pièce redevient non rattachée.

## Gestion d'erreur

- Échec du PATCH : géré par le mécanisme d'erreur global existant des mutations (toast). Le select revient à la valeur serveur au prochain re-fetch.
- `typeNames` vide (objectif pas encore synchronisé / chargé) : le select n'affiche que l'option vide ; aucune action destructrice.

## Tests

Test composant focalisé (vitest + jsdom, mocks `@/lib/queries/garderobe`) :
- Le select rend la valeur courante `v.type_objectif` d'une pièce.
- Sélectionner un type déclenche `useUpdateVetement().mutate` avec `{ id, patch: { type_objectif: <nom> } }`.
- Sélectionner l'option vide déclenche `mutate` avec `type_objectif: null`.

## Décomposition

Une seule unité de travail (1 fichier composant modifié + 1 fichier de test). Pas de découpage multi-tâches nécessaire.
