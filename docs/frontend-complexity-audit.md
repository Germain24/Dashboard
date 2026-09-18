# Audit de complexité du frontend

Date : 2026-09-06

## Mesure de référence

- 415 fichiers JavaScript/TypeScript dans `frontend` (sources, tests et scripts).
- La première passe stricte recensait 480 problèmes ; une passe complète ultérieure
  recensait 437 problèmes avant les lots Budget et primitives UI ci-dessous.
- L’ESLint ne fixe pas encore de seuil cyclomatique dans sa configuration.
- Mesure de la règle `complexity` avec un maximum de 4 sur `components`, `src` et
  `lib` : 98 violations dans `components/finance`.

## Plus gros points de complexité dans Finance

| Fichier | Fonction | Complexité |
| --- | --- | ---: |
| `components/finance/BuffettRunDetailView.tsx` | `BuffettRunDetailView` | 144 |
| `components/finance/BuffettTab.tsx` | `BuffettTab` | 62 |
| `components/finance/DeStarrChart.tsx` | `DeStarrChart` | 47 |
| `components/finance/SuiviTab.tsx` | `SuiviTab` | 44 |
| `components/finance/TransactionsTab.tsx` | `TransactionsTab` | 43 |
| `components/finance/BuffettActionsPanel.tsx` | `BuffettActionsPanel` | 26 |

## Stratégie de réduction

1. Extraire les blocs de rendu en composants spécialisés, sans modifier les
   contrats API ni les états affichés.
2. Extraire les transitions d’état et les handlers en fonctions pures/hooks
   dédiés ; remplacer les chaînes de conditions par des tables de configuration.
3. Commencer par le parcours Buffett, car il est actuellement observé en live,
   puis Finance, Budget, Santé, Voyage et les composants communs.
4. Ajouter `complexity: ["error", 4]` dans ESLint uniquement lorsque chaque lot
   concerné est sous le seuil ; les erreurs de typage, hooks et accessibilité
   resteront suivies séparément.

## État local observé

- Lot 1 réalisé : le rendu du tab Buffett est séparé en contenu, progression,
  timeline et utilitaires d’état ; ces nouveaux composants respectent la
  complexité maximale 4.
- Lot 2 réalisé : les callbacks SSE, le polling de rattrapage et les actions
  utilisateur sont isolés dans des modules dédiés ; les 7 fichiers du parcours
  Buffett passent désormais la règle `complexity: 4`.
- Lot 3 réalisé : les fondations partagées (`lib/api`, navigation par onglet,
  fraîcheur et greeting) passent également la règle `complexity: 4`. Le client
  HTTP conserve le timeout, l’annulation appelant et le parsing des erreurs.
- Lot 4 réalisé côté Finance : `DeStarrChart` est séparé en synchronisation
  d’historique, calcul du modèle, SVG, marqueurs, détails et légende ; il passe
  désormais la règle `complexity: 4` sans modifier les 14 tests de la courbe.
- Lot 5 réalisé : `BuffettRunDetailView` est séparé en actions, cellules
  d’allocation et section look-through ; la vue principale et ses sous-sections
  passent la règle `complexity: 4`.
- Lot 6 réalisé : `budget/MoisTab` est séparé en hook de données, synthèse,
  graphiques/prévision, intégrations et enveloppes ; le composant initial à 56
  passe désormais la règle `complexity: 4`.
- Lot 7 réalisé : les primitives `DataTable`, `ChartFrame`, `StatCard`,
  `CollapsibleSection` et le client `lib/finance` sont découpés et passent la
  règle stricte ciblée.
- Lot 8 réalisé : `cuisine/MoisTab`, `RecettesTab`, `GardeMangerTab` et
  `RecipeDetailModal` passent désormais la règle `complexity: 4`; le détail
  recette n’a plus de synchronisation d’état immédiate signalée par React.
- Lot 9 réalisé : `cuisine/RecipeForm`, `CoursesTab` et `PlanSemaineTab` sont
  maintenant séparés en modèles/hooks et composants de rendu spécialisés ;
  les six fichiers du lot passent la règle stricte `complexity: 4`.
- Lot 10 réalisé : l’orchestrateur `agenda/Agenda` et la liste `TachesTab`
  sont séparés en indicateurs, sélection d’onglet, formulaire et lignes de
  tâche ; les fichiers du lot passent la règle stricte `complexity: 4`.
- Lot 11 réalisé : les pages Budget, Cuisine et Habitudes utilisent une table
  de rendu d’onglets, et l’orchestrateur Voyage délègue ses contrôles d’état ;
  les fichiers concernés passent également la règle stricte.
- Lot 12 réalisé : `agenda/JourTab` délègue le calcul des événements, le badge
  de séance et la timeline ; le composant passe la règle stricte `complexity: 4`.
- Lot 13 réalisé : `agenda/MoisTab`, `agenda/SemesterTab` et
  `budget/SubscriptionAlerts` délèguent leurs cellules/listes et passent la
  règle stricte `complexity: 4`.
- Lot 14 réalisé : `agenda/SemaineTab` délègue la barre d’outils, les filtres,
  les états et la grille horaire ; navigation, conflits et synchronisations
  restent couverts par le même contrat et passent `complexity: 4`.
- Lot 15 réalisé : les utilitaires `lib/agenda` (`planFocus`, export iCal et
  détection de chevauchements) sont découpés en helpers testables et passent
  également la règle stricte.
- Lot 16 réalisé : `lib/cuisine.fetchRecipes` délègue la construction de ses
  paramètres de recherche et passe la règle stricte.
- Lot 17 réalisé : `sante/Sante` et `TendanceTab` délèguent l’état, les actions,
  les cartes de statistiques et le SVG de tendance ; ils passent `complexity: 4`.
- Lot 18 réalisé : `sante/SleepWidget` et `WorkoutBurnWidget` délèguent leurs
  états d’affichage et sous-composants ; ils passent la règle stricte.
- Lot 19 réalisé : `voyage/PlanifierTab`, `LieuxTab` et `ItineraryMap` délèguent
  formulaire, résultat, lignes de lieux et validation des coordonnées ; ils
  passent `complexity: 4` sans modifier les mutations de planification.
- Lot 20 réalisé : la palette de commandes, la navigation mobile, les
  raccourcis clavier et leur déclencheur délèguent désormais leurs handlers,
  recherches, résultats et sous-vues ; ils passent `complexity: 4`. Le
  déclencheur utilise aussi une souscription React compatible SSR au lieu d’un
  `setState` immédiat dans un effet.
- Lot 21 réalisé : `ObjectifsVie` délègue le formulaire, les jalons et la
  liste ; `RealtimeProvider` sépare le parsing, l’invalidation et la
  notification ; `ShortcutsHelp` sépare l’ouverture, le focus et le rendu.
  Les comportements couverts restent inchangés et les trois fichiers passent
  `complexity: 4`.
- Lot 22 réalisé : `voyage/PlanifierAutoTab` et `VoyagesConfirmesTab` délèguent
  maintenant leurs formulaires, calculs de destination, cartes d’itinéraire,
  coûts réels et checklist ; ils passent `complexity: 4`.
- Lot 23 réalisé : la page `Snapshot` délègue les widgets bien-être, historique,
  time machine, budget d’énergie et heatmap annuelle ; elle passe
  `complexity: 4` sans modifier les requêtes.
- Lot 24 réalisé : `sante/FenetreTab` est séparé en contrôleur, états de
  génération et sections de rendu ; les clients JSON partagent maintenant un
  parseur d’erreur commun. Le lot retire 5 problèmes de la mesure stricte.
- Lot 25 réalisé : l’orchestrateur `entrainement/Entrainement`, l’onglet
  Aujourd’hui et `SlotCard` délèguent leurs données, actions et sections de
  rendu ; les fichiers du lot passent `complexity: 4`.
- La mesure globale après le lot 25 est de 363 problèmes (332 erreurs, 31
  avertissements), contre 480 au départ. Les lots suivants ciblent encore les
  écrans Routines, Agenda, Voyage, Santé et les pages d’application plutôt que
  d’ajouter une exception globale dans ESLint.
- Les serveurs frontend/backend ont été arrêtés pendant le refactoring, comme
  demandé ; ils seront relancés pour la vérification navigateur finale.
- Run actif : `run_id=73`, phase `preparation`, `0 / 257499` ; la phase
  `optimisation` est encore idle, donc aucune courbe d’optimisation n’est encore
  disponible dans le dashboard.
