# Planificateur de voyages — Design

**Date :** 2026-07-01
**Statut :** approuvé (design)

## Objectif

Nouveau module **Voyage** : à partir de la liste des lieux à visiter dans une vie (`data/imports/Voyage.xlsx`, 125 lieux existants), et de contraintes données à la volée (dates disponibles, lieu de départ, lieu d'arrivée, budget), proposer l'itinéraire qui **maximise le nombre de lieux visités** tout en respectant temps et budget.

## Portée (v1)

Planification **d'un seul voyage à la fois** — pas de répartition automatique de toute la liste sur plusieurs années. L'utilisateur relance l'outil à chaque nouveau voyage.

## 1. Données d'entrée — extension de `Voyage.xlsx`

Colonnes existantes : `Lieux`, `Ville (ou ville la plus proche)`, `Pays`, `Visité` (bool), `Ordre` (sens inconnu, ignoré par l'algorithme — non touché).

Nouvelles colonnes ajoutées :

| Colonne | Rôle |
|---|---|
| `Aéroport (IATA)` | code aéroport le plus proche du lieu — nécessaire pour interroger l'API de vols |
| `Jours min` | durée minimale de séjour acceptable sur place |
| `Jours max` | durée maximale de séjour acceptable sur place |
| `Coût/jour estimé` | hébergement + repas + activités (€), estimé manuellement par lieu |

`Visité=True` exclut automatiquement un lieu des candidats. Import/sync suit le pattern déjà établi par `Vetements.xlsx` : backup horodaté avant écriture, table cache en DB (`lieu_voyage`), bouton « Re-synchroniser l'Excel » côté front. Les lignes sans `Aéroport (IATA)` ou sans `Jours min/max` renseignés sont exclues des candidats (pas de valeur par défaut inventée) et remontées comme « incomplet » dans la réponse de sync, sur le même principe que `non_rattaches` de l'onglet Objectif garde-robe.

## 2. Requête de planification

Saisie à chaque appel (non stockée dans l'Excel — un formulaire de recherche, pas un enregistrement persistant) :

- `date_debut`, `date_fin`
- `depart_iata` (défaut : aéroport de Montréal — cohérent avec `GARDEROBE_LAT/LON`)
- `arrivee_iata` (défaut = `depart_iata`, override possible pour un trajet non bouclé)
- `budget_total`
- `candidats` : sous-ensemble de lieux à considérer — filtre par pays/continent ou sélection manuelle explicite d'IDs. **Obligatoire et plafonné à 25 lieux** (voir § Limites).

## 3. Récupération des trajets — Duffel

Amadeus ferme son portail self-service le 2026-07-17 ; Kiwi Tequila et Travelpayouts/Aviasales exigent désormais ≥50 000 utilisateurs actifs/mois pour la recherche temps réel, inutilisables pour un usage personnel. **Duffel** est retenu : inscription libre, SDK Python officiel (`duffel-api`), pas de seuil d'utilisateurs, offres de vols réelles (prix + durée) accessibles en mode test sans accréditation IATA.

Pour chaque paire de lieux candidats (+ départ/arrivée), une requête Duffel donne prix + durée. **Simplification assumée** : une seule requête par paire, à `date_debut` comme date de référence — pas de recalcul selon la position réelle de l'étape dans l'itinéraire (variation mineure face à l'optimisation qualitative). Résultats mis en cache dans une table `duffel_cache` (clé : paire d'aéroports + date de référence) pour ne pas re-interroger l'API entre deux essais de la même requête.

Clé `DUFFEL_API_KEY` optionnelle dans `.env` ; le module dégrade proprement (erreur explicite « clé Duffel manquante », pas de plantage) si absente, comme les autres intégrations du projet.

## 4. Moteur d'optimisation — OR-Tools CP-SAT

Nouvelle dépendance `ortools`. Modélisation comme un **circuit optionnel** : chaque lieu candidat est soit intégré au chemin `depart → … → arrivee`, soit exclu via une boucle sur lui-même (pattern standard CP-SAT `AddCircuit` pour un TSP avec sélection de nœuds — ici asymétrique, chemin ouvert plutôt que tournée fermée).

Variables :
- `visite[i] ∈ {0,1}` par lieu candidat
- `duree[i] ∈ [jours_min[i], jours_max[i]]` si `visite[i]=1`
- arcs du circuit optionnel (ordre de parcours)

Contraintes :
- `Σ duree[i] (visités) + Σ durée des trajets empruntés ≤ (date_fin - date_debut)`
- `Σ coût trajets empruntés + Σ coût/jour[i] × duree[i] (visités) ≤ budget_total`

Objectif : `maximiser Σ visite[i]`.

Fonction pure et testable : `solve_itinerary(candidats, distances, budget_total, jours_disponibles, depart, arrivee) -> Itineraire | None` (None si aucune combinaison ne satisfait les contraintes, ex. budget trop faible pour même relier départ→arrivée).

## 5. Sortie

- Liste ordonnée des lieux retenus avec durée assignée et dates estimées (calculées séquentiellement depuis `date_debut`)
- Coût total, détaillé transport vs séjour
- Lieux candidats non retenus (et pourquoi ils ont été écartés n'est **pas** garanti — CP-SAT ne motive pas ses exclusions, on affiche juste "non retenu")
- Action « Confirmer ce voyage » : marque les lieux retenus `Visité=True` dans le cache DB (et à la prochaine resync Excel, propage l'écriture dans le fichier — même mécanique que les autres masters Excel du projet)

## 6. Intégration technique

Conventions existantes respectées :
- `backend/app/models/voyage.py` (`LieuVoyage`, cache `duffel_cache`)
- `backend/app/services/voyage/` : `import_excel.py` (sync), `duffel_client.py` (appels + cache), `solver.py` (fonction pure OR-Tools)
- `backend/app/api/voyage/` : endpoints sync, recherche de candidats (filtre pays/continent), planification, confirmation
- `frontend/components/voyage/` : liste des lieux (avec filtre + statut Visité), formulaire de requête, affichage de l'itinéraire résultat
- Nouvelles dépendances Python : `ortools`, `duffel-api`

## Limites connues (v1)

- **Candidats plafonnés à 25 par requête** : au-delà, le nombre de paires à interroger auprès de Duffel (O(n²)) devient impraticable (125 lieux → ~15 500 paires). L'utilisateur doit pré-filtrer (pays/continent/sélection manuelle) avant de lancer une planification.
- **Prix de vol approximatif** : un seul point de prix par paire (date de début du voyage), pas de recherche de la meilleure date à l'intérieur de la fenêtre.
- **Pas de répartition multi-voyages** : chaque appel planifie un voyage isolé ; rien ne suit un objectif "visiter toute la liste d'ici N années".
- **Transport terrestre non modélisé** : uniquement des trajets aériens via Duffel (pas de train/bus/voiture — pertinent pour des lieux proches, ex. deux villes européennes).

## Tests

- `solver.py` (fonction pure) : cas simple 3 candidats où le budget ne permet d'en retenir que 2 (vérifie que le bon sous-ensemble est choisi) ; cas où la fenêtre de jours est trop courte pour visiter quoi que ce soit (retourne None) ; respect des `jours_min/max` par lieu retenu ; départ ≠ arrivée.
- `duffel_client.py` : cache — deux appels pour la même paire+date ne déclenchent qu'une requête Duffel (mock du SDK) ; clé absente → erreur explicite, pas de crash.
- `import_excel.py` : sync détecte les lignes incomplètes (IATA ou jours manquants) et les exclut des candidats ; `Visité=True` filtré ; backup horodaté créé avant écriture (même pattern que `objectif_import.py`).
- API : endpoint de planification bout-en-bout avec Duffel et OR-Tools mockés (déterministe, pas d'appel réseau en test) ; endpoint de confirmation marque bien `Visité=True` en DB.

## Décomposition

1. Modèle `LieuVoyage` + import Excel (colonnes étendues, backup, détection incomplets) + tests.
2. `duffel_client.py` (appel + cache) + tests (SDK mocké).
3. `solver.py` (OR-Tools, fonction pure) + tests (cas budget/temps serrés, départ≠arrivée).
4. API : sync, filtre candidats, planification, confirmation + tests bout-en-bout (dépendances mockées).
5. Frontend : liste des lieux + formulaire de requête + affichage itinéraire.

Sous-projet cohérent unique, mais plus gros que la moyenne des specs du projet (nouvelle dépendance solveur + nouvelle intégration externe) — à surveiller si la décomposition ci-dessus doit être scindée en plusieurs plans d'implémentation successifs plutôt qu'un seul.
