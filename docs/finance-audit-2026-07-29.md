# Audit Finance — 2026-07-29

## Périmètre

Portefeuille, cours, change, fiscalité, historique, objectifs patrimoniaux et
pipeline Buffett. L'audit est statique et couvert par les suites
`backend/tests/test_finance`; aucune formule financière n'a été modifiée sans
test de non-régression.

## Résultats

- **Portefeuille et historique** : les cours sont récupérés en lots et le cache
  de `prices.py` empêche un nouvel appel Yahoo à chaque chargement. Les snapshots
  et historiques utilisent les valeurs persistées; aucun appel réseau n'est
  nécessaire pour lire l'historique.
- **FX** : les conversions vers EUR sont centralisées, mises en cache par paire
  et réutilisées par le volume, le risque et l'optimisation. Les tests couvrent
  les devises inconnues, les volumes convertis et les rendements en devise de
  base.
- **Fiscalité** : le calcul PMP, les moins-values reportables, dividendes,
  retenues à la source, PFU et barème sont couverts. Les cessions incomplètes
  restent exclues avec un avertissement au lieu d'être estimées silencieusement.
- **Objectifs patrimoniaux** : les montants sont consolidés en EUR avant calcul
  de progression. Les scénarios liberté financière et Japon sont déterministes.
- **Buffett** : les résultats et la progression sont maintenant écrits par lots;
  une reprise utilise un snapshot immuable. Le cache primaire SQLite sépare les
  métadonnées quotidiennes des fondamentaux par ISIN/exercice.

## Points corrigés

1. Suppression directe de tickers remplacée par une quarantaine structurée.
2. Reprise sur CSV courant remplacée par un snapshot avec checksum.
3. Commits SQLite par ticker remplacés par des lots de 50 et une progression
   publiée au plus tous les 50 tickers ou cinq secondes.
4. Polling de l'optimiseur limité aux phases `preparation` et `optimisation`.
5. Suspension de la machine exclue de l'ETA; la session Yahoo est renouvelée au
   réveil.

## Points dépendant des données externes

- La reconstruction mondiale complète nécessite encore les exports officiels
  absents du dossier courant (SSE, SZSE, HKEX, JPX, ASX, LSE et autres places).
- La validation Yahoo est disponible en lots via `--validate-yahoo`; un symbole
  officiellement coté mais non résolu doit rester une erreur de mapping, jamais
  une preuve suffisante de délistage.
