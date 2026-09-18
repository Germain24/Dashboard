# Audit du moteur de portefeuille — 15 septembre 2026

## Corrections

- Recherche : conserver des portefeuilles clairsemés lors des perturbations,
  financer les nouvelles positions avec le capital libéré, et affiner les poids
  par transferts locaux pour sortir des plateaux sans changer tout le portefeuille.
- Score : harmoniser le calcul du risque extrême scalaire/vectorisé, respecter
  le cash non investi, et comparer les candidats après arrondi avec le même
  objectif complet et les mêmes contraintes.
- Exécution : utiliser les mêmes cours des cotations réellement accessibles
  chez chaque courtier pour évaluer et construire l'allocation. Une cotation
  secondaire sans prix ne reprend pas arbitrairement le prix de la principale.
- Allocation : protéger les calculs contre les prix non finis, tenir compte des
  secteurs internes des ETF et réinvestir le capital libéré dans les limites.
- Persistance : conserver ensemble l'allocation gagnante, son score et ses
  diagnostics ; une tentative rejetée ne remplace plus ses diagnostics.
- Préparation : conserver les pays des actions, ne pas attribuer d'accès à un
  courtier absent du catalogue, traiter prudemment les corrélations inconnues,
  et signaler les échecs de préparation comme erreurs.
- ETF : les appels de préparation ne forcent plus les téléchargements et ne
  contournent plus les délais de reprise des erreurs. Un TER absent ne suffit
  plus à relancer une tentative récente. Les métadonnées sont résolues pour le
  lot demandé, pas pour tout le catalogue. Une composition officielle physique
  ou un proxy admissible déjà disponible évite une recherche d'indice superflue.
  L'arrêt demandé est transmis aux connecteurs fonds et indices.

## Vérifications

- Suite ciblée compositions/connecteurs/création/exécution : 89 tests réussis.
- Suite finale score/recherche/persistance/allocation/sélection/cache ETF :
  99 tests réussis, dont les cas avec et sans ETF et un optimum de référence
  obtenu par grille exhaustive sur un univers synthétique de deux actifs.
- Interface : 7 tests réussis sur la progression et le détail des compositions.
- Suite élargie robustesse/exploration/progression : 150 tests réussis.
- Dernière vérification cache ETF/cotations/création : 18 tests réussis ; routage
  et pays : 5 tests réussis. Compilation des modules modifiés et `git diff
  --check` réussis. Les suites se recouvrent ; ces nombres ne sont pas à sommer.
- Deux essais hors ligne sur 1 295 observations issues des caches locaux :
  10 actions, puis 10 actions et 3 ETF, 20 générations chacun. Les deux produisent
  une allocation exécutable admissible, avec environ 99,94 % et 99,77 % du budget
  investi respectivement. Budgets et univers de test contrôlés ; aucun ordre
  transmis et aucune allocation personnelle remplacée.

## Limites

Ces essais ne prouvent pas un optimum global ni un rendement futur. Les scores
dépendent de l'univers, du benchmark, des historiques et des contraintes.
Les tests de connecteurs utilisent des réponses simulées : ils ne certifient
pas la disponibilité actuelle de tous les sites émetteurs.

Certains indices restent sous licence ou sans source exploitable. Le correctif
évite de répéter inutilement leurs échecs ; il ne fabrique pas leur composition
et ne traite pas le collatéral d'un ETF synthétique comme son indice.

Les allocations anciennes ne sont pas réécrites automatiquement. Redémarrer
le backend puis lancer une nouvelle génération permet d'utiliser ces corrections.
