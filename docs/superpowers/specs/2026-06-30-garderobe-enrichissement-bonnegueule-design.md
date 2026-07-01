# Enrichissement des échelles — marques FR intermédiaires (BonneGueule) — Design

**Date :** 2026-06-30
**Statut :** approuvé (design)

## Objectif

Enrichir les échelles de `data/imports/Vetements.xlsx` avec les marques **françaises intermédiaires** que BonneGueule champione et qui manquent aujourd'hui (les listes actuelles sont déjà riches mais très japonaises/anglo-saxonnes, sans marque FR mid-tier). Chaque marque est insérée **juste après la marque d'entrée** (le rang « intermédiaire accessible »).

## Décisions

- **Source = curation** (informée BonneGueule), pas de scraping : les favorites BonneGueule sont déjà dans les échelles ; le vrai manque est le mid-tier français, que l'on connaît.
- **Portée ciblée** : uniquement les types où une marque FR intermédiaire crédible existe (~33 des 55). Aucun remplissage forcé ailleurs.
- **Master gitignoré** : `data/imports/Vetements.xlsx` n'est pas suivi par git → la modification est locale (non committée). On commite le script + la table + les tests.
- **Sécurité** : backup horodaté avant écriture ; diff avant/après ; re-sync du cache objectif après écriture ; réversible.

## Règle d'insertion

`insert_after_entry(echelle, brands)` :
- conserve `echelle[0]` (marque d'entrée) ;
- des `brands`, ne garde que celles absentes de `echelle` (comparaison insensible à la casse/espaces) et dédupliquées entre elles, dans l'ordre donné ;
- résultat = `[echelle[0]] + nouvelles + echelle[1:]` ;
- si `echelle` est vide → renvoie les `brands` dédupliquées ; si un seul élément → insère après.

## Table d'enrichissement (à valider)

`ENRICHMENT: dict[str, list[str]]` — type objectif → marques FR à insérer :

**Hauts**
- T-shirts : Loom, Asphalte, Le Minor
- Polos : Asphalte, Le Minor
- Chemises : Asphalte, Officine Générale, De Bonne Facture
- Débardeurs : Le Minor, Saint James
- Pulls : Officine Générale, De Bonne Facture, Maison Montagut
- Sweats : Asphalte, Maison Labiche
- Gilets : Officine Générale, De Bonne Facture
- Overshirts : Asphalte, De Bonne Facture

**Bas**
- Jeans : Asphalte, 1083, Ateliers de Nîmes
- Pantalons chino : Asphalte, Officine Générale, De Bonne Facture
- Pantalons habillés : Officine Générale, De Fursac, Husbands
- Shorts : Asphalte
- Pantalons en velours : Officine Générale, De Bonne Facture

**Vestes / manteaux**
- Vestes légères : Officine Générale, De Bonne Facture, Harmony
- Blazers : Officine Générale, De Fursac, Husbands
- Manteaux : Officine Générale, Harmony, Éditions M.R

**Costume**
- Vestes de costume : De Fursac, Husbands, Samson
- Pantalons de costume : De Fursac, Husbands
- Gilets de costume : De Fursac, Husbands
- Smokings : De Fursac, Husbands

**Sous-vêtements**
- Boxers : Le Slip Français
- Slips : Le Slip Français
- Maillots de corps : Le Slip Français
- Chaussettes : Bleuforêt, Labonal, Royalties

**Chaussures**
- Bottines : Jules & Jenn, Anthology Paris
- Chaussures de ville : Bexley, Jacques & Déclercq, Markowski

**Accessoires**
- Ceintures : JOSEPH BONNIE, Bleu de Chauffe
- Cravates : Le Colonel Moutarde, Cinabre
- Nœuds papillon : Le Colonel Moutarde, Cinabre
- Foulards : Cinabre
- Lunettes de soleil : Jimmy Fairly, Ateliers Loden
- Sacs à dos : Bleu de Chauffe, Bonastre, Côme
- Sacs de voyage : Bleu de Chauffe, Bonastre
- Portefeuilles : Bleu de Chauffe, JOSEPH BONNIE

**Technique**
- Maillots techniques : Circle Sportswear
- Shorts techniques : Circle Sportswear

**Types NON enrichis** (pas de bon candidat FR mid-tier) : Pantalons cargo, Jogging, Vestes en cuir, Parkas, Doudounes, Coupe-vent/Imperméables, Baskets, Sandales, Écharpes, Gants, Bonnets, Casquettes, Chapeaux, Pyjamas, Peignoirs, Shorts de nuit, Leggings de sport, Vêtements de compression, Vestes de sport.

## Moteur

Nouveau `backend/scripts/enrich_bonnegueule.py` :
- fonction pure `insert_after_entry(echelle: list[str], brands: list[str]) -> list[str]` (dédup insensible casse/espaces).
- table `ENRICHMENT` (ci-dessus).
- `main()` :
  1. backup `data/imports/Vetements.xlsx` → `Vetements.backup-<YYYYmmdd-HHMMSS>.xlsx` (même dossier).
  2. ouvre le workbook (writable, openpyxl) ; pour chaque ligne dont le type ∈ ENRICHMENT : lit l'échelle (col C.. jusqu'à la dernière non vide), calcule `insert_after_entry`, réécrit les cellules (col C.. ) et vide les cellules résiduelles au-delà de la nouvelle longueur ; conserve col A (type) et B (quantité).
  3. sauvegarde le workbook.
  4. imprime un diff par type enrichi (avant → après) + le nombre de marches ajoutées.
- idempotent : re-lancer ne duplique pas (dédup insensible casse).

## Flux

1. `uv run python -m scripts.enrich_bonnegueule` → backup + écriture + diff.
2. `POST /garderobe/objectif/sync` (ou re-sync bouton) → le cache `objectif_type` reflète les nouvelles échelles ; les positions des pièces sur la barre 0→100 se recalculent (une marque possédée conserve son rang relatif ; l'échelle plus longue peut décaler les positions — comportement attendu).
3. Réversible : restaurer le backup + re-sync.

## Gestion d'erreur / cas limites

- Type de l'ENRICHMENT absent du fichier → ignoré (log).
- Marque déjà présente → non ré-insérée (dédup).
- Échelle vide pour un type → insère les marques (peu probable ici).

## Tests

- Backend purs (`insert_after_entry`) : insertion après l'entrée, dédup vs existant (casse/accents), dédup entre nouvelles, ordre préservé, échelle vide / à un élément.
- (Le `main()`/écriture Excel est vérifié par le run réel : diff imprimé, backup créé, re-lecture confirme les insertions ; pas de test unitaire sur openpyxl-write — comme les autres scripts one-time du projet.)

## Décomposition

1. `insert_after_entry` (pure) + table `ENRICHMENT` + tests.
2. Script `main()` (backup + écriture Excel + diff) + run réel + re-sync + vérification.

Sous-projet cohérent unique (données + petit script).
