# Récupération des compositions ETF — 16 septembre 2026

## Changements

- **Vanguard** : résolution ISIN depuis les identifiants du catalogue officiel,
  y compris les nouveaux identifiants `E…`, au lieu de rechercher seulement
  les numéros 9000–9999. Annuaire partagé pendant une heure, protégé contre
  les chargements concurrents. Les positions obligataires sont désormais
  récupérées ; les liquidités et dérivés ne sont pas assimilés à des actions.
- **HSBC** : fiche officielle vérifiée par ISIN, méthode de réplication et nom
  d'indice lus dans cette fiche, puis récupération du fichier complet de positions
  pour les fonds explicitement physiques. Lecture des fichiers Excel binaires
  `.xls` avec la dépendance `python-calamine` déjà déclarée.
- **Pondérations** : une seule unité par colonne. Auparavant, dans certains
  fichiers, 8 % était converti correctement mais 0,2 % devenait 20 %.
- **Indices/synthétiques** : le collatéral reste exclu. Un fichier simplement
  intitulé « Fund constituents » n'est plus classé comme composition d'indice.
  Un proxy physique est explicitement identifié et doit suivre le même panier ;
  une variante ESG n'est pas substituée à l'indice standard.
- **Reprise** : une nouvelle révision du connecteur permet de retenter un ancien
  échec une fois, sans supprimer ensuite les délais de reprise. Les erreurs
  réseau réelles sont conservées dans les diagnostics au lieu d'être masquées
  par « fiche introuvable ».

## Résultats observés

Une relance bornée de **24 fonds précédemment en erreur** a mis à jour le cache :
**13 compositions complètes récupérées**, représentant **32 cotations** du
catalogue ; 1 composition partielle ; 10 cas encore indisponibles. Les échecs
restants incluent des identifiants absents du catalogue européen Vanguard et
des fonds HSBC dont la méthode n'est pas publiée dans le champ attendu.
Les ETF actifs HSBC ne sont pas assimilés arbitrairement à leur benchmark.

Essais HTTP directs supplémentaires, sans écriture d'allocation :

| Fonds | Positions récupérées | Couverture |
| --- | ---: | ---: |
| HSBC Hang Seng Tech, IE00BMWXKN31 | 30 | 99,29 % |
| HSBC MSCI World, IE00B4X9L533 | 1 231 | 99,93 % |
| Vanguard ESG Emerging Markets, IE0001VXZTV7 | 3 828 | 97,39 % |
| Vanguard Eurozone Government 1–3 Year, IE00004S2680 | 87 | 99,95 % |

Sources utilisées : [documents officiels HSBC](https://www.assetmanagement.hsbc.co.uk/en/intermediary/funds/ie00bmwxkn31),
[catalogue officiel Vanguard](https://www.vanguard.co.uk/professional/product).
Les chiffres ci-dessus mesurent les réponses effectivement reçues pendant les
essais, pas une promesse de disponibilité future.

## Vérification et exploitation

- Suite connecteurs/registre/expositions : 101 tests réussis.
- Suite connecteurs/reprise/lots après amélioration des diagnostics : 60 tests réussis.
- Vérification finale connecteurs et distinction fonds/indice : 47 tests réussis.
  Ces suites se recouvrent et ne sont pas à additionner.
- Tests dédiés : identifiants alphanumériques, cache de découverte, ISIN incorrect,
  exclusion du collatéral, petites pondérations, Excel sans extension, obligations,
  reprise après changement de connecteur, proxy exact et couverture insuffisante.

Script de maintenance, depuis `backend` :

```powershell
.\.venv\Scripts\python.exe scripts/retry_repaired_etf_connectors.py --limit 24
.\.venv\Scripts\python.exe scripts/retry_repaired_etf_connectors.py --limit 24 --apply
```

Sans `--apply`, le script ne fait que prévisualiser. `--retry-recent` est réservé
à une relance explicite de maintenance ; il n'est pas utilisé par l'optimisation.
Les restrictions réseau de l'environnement de test ont nécessité une autorisation
pour la relance réelle. Aucun ordre ni aucune allocation personnelle n'a été modifié.

La couverture de positions n'est pas à elle seule une admission dans le solveur :
les contrôles pays/secteurs, de fraîcheur et de disponibilité chez le courtier
restent applicables. Tous les émetteurs n'ont pas été réparés ni retestés en ligne.

## Préparation bornée et indices équivalents

Le journal fourni montre un inventaire réseau du catalogue puis plusieurs vagues
de remplacement (346, 61, 13, 6, 5 rejets). La préparation Buffett utilise désormais
un inventaire local uniquement. Les recherches réseau sont réservées aux candidats
sélectionnés et à un éventuel tracker physique du même panier.

Limites dans `buffett/config.py`, partagées entre les vagues et entre workers :

- 3 vagues maximum ; 24 identités de fonds et 12 paniers d'indices recherchés.
- 80 appels réseau maximum ; délai partagé de 180 secondes à partir de la première
  recherche. Aucun nouvel appel n'est autorisé après son expiration.
- Timeout réseau plafonné à 10 secondes et au temps restant. Les transferts déjà
  engagés, redirections HTTP, traitements PDF/Excel et sauvegardes peuvent dépasser
  le délai : ce n'est pas une limite de trois minutes pour l'ensemble du run.

Les ETF vérifiés et les actions restent admissibles ; les ETF non vérifiés ne
sont jamais promus après la dernière vague. L'épuisement du budget n'est pas
enregistré comme une panne permanente de l'émetteur ou de l'indice. Les diagnostics
`research_budget` donnent les compteurs et les plafonds. La maintenance explicite
des connecteurs reste indépendante de cette préparation interactive.

Les compositions récentes sont réutilisées avant toute recherche. Les lectures
du registre sont mutualisées au sein d'un lot, et la résolution du catalogue ne
parcourt en détail que les lignes demandées. Une liste fermée d'équivalences
reconnaît notamment MSCI Monde/World, Marchés émergents/EM/Emerging Markets,
ACWI/All Country World, S & P/S&P et certaines conventions de rendement traduites.
Les variantes ESG/SRI, équipondérées, petites capitalisations, levier et exclusions
géographiques restent distinctes ; la sélection conserve les couvertures de change.
Des identifiants officiels de fournisseur contradictoires interdisent le partage
de composition, même si les noms correspondent.

Pour un synthétique, le panier de l'indice reste l'exposition recherchée. Un tracker
physique du même panier est utilisable comme proxy explicitement identifié,
avec les contrôles existants de fraîcheur/couverture ; le collatéral ne l'est pas.

Ces changements nécessitent un redémarrage du backend et une nouvelle préparation.
Ils ne modifient pas le processus déjà lancé et ne nécessitent aucune migration.

Validation hors réseau : 165 tests réussis (budgets, cache, alias, connecteurs,
sources manuelles, lots de remplacement, exposition et préparation du portefeuille).
Le temps total d'une nouvelle exécution réelle n'a pas été mesuré ; le calcul en
cours de l'utilisateur n'a pas été interrompu pour ces vérifications.
