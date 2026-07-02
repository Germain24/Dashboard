# Carte de l'itinéraire conseillé — Design

**Date :** 2026-07-02
**Statut :** approuvé (design)

## Objectif

Dans l'onglet Planifier du module Voyage, afficher le résultat de `POST /voyage/planifier` (l'itinéraire recommandé) sur une carte — en plus de la liste ordonnée déjà existante — pour visualiser d'un coup d'œil le trajet départ → lieux retenus → arrivée.

## Portée (v1)

Visualisation uniquement, de l'itinéraire recommandé courant. Pas de sélection interactive, pas d'affichage de la wishlist complète, pas de persistance de l'état de la carte.

## 1. Données — table locale IATA → coordonnées

Aucune coordonnée lat/lon n'existe aujourd'hui dans le projet (`LieuVoyage`, `Voyage.xlsx`, réponse `/planifier`) — seuls `ville`, `pays` et `aeroport_iata` sont disponibles.

Nouveau fichier statique committé `backend/app/services/voyage/data/airports_iata.csv`, dérivé du dataset public domain [OurAirports](https://ourairports.com/data/) (CC0), filtré aux entrées ayant un code IATA renseigné (~9-11k aéroports), réduit aux colonnes `iata,name,lat,lon`. Chargé une seule fois en mémoire (`dict[str, tuple[float, float]]`) au premier accès, dans le même style paresseux que `import_excel.py`. Aucun appel réseau, déterministe, cohérent avec l'esprit « données locales » du projet.

Un code IATA absent de la table (rare — ce sont des codes déjà saisis/validés dans `Voyage.xlsx`) donne un lookup `None`, jamais une exception.

## 2. Backend — enrichissement de la réponse `/voyage/planifier`

Ajouts aux schémas Pydantic (et à leurs équivalents TypeScript) :

- `EtapeItineraire` gagne `lat: float | None` et `lon: float | None`.
- `ItineraireOut` gagne `depart: PointItineraire` et `arrivee: PointItineraire`, avec `PointItineraire = {iata: str, lat: float | None, lon: float | None}`.

`post_planifier` fait le lookup IATA → coordonnées pour chaque point (départ, chaque étape retenue, arrivée) juste avant de construire la réponse — un dict lookup local, pas de requête réseau supplémentaire, pas d'impact sur le solveur ni sur le calcul Duffel existants.

Si un point n'a pas de coordonnées (IATA absent de la table), `lat`/`lon` restent `None` pour ce point — la réponse `/planifier` reste valide (200), aucune erreur 500. Le frontend décide alors s'il affiche la carte (§3).

## 3. Frontend — composant carte

Nouveau composant `frontend/components/voyage/ItineraryMap.tsx` (`"use client"`), basé sur `react-leaflet` + `leaflet` (tuiles OpenStreetMap, pas de clé API requise) — nouvelles dépendances npm. Importé dans `PlanifierTab.tsx` via `next/dynamic({ ssr: false })` pour éviter les erreurs de rendu serveur de Leaflet (accès à `window` au chargement).

**Contenu :**
- Un marqueur par point, dans l'ordre réel du parcours : départ → étapes (dans l'ordre retenu par le solveur) → arrivée.
- Une polyligne reliant les marqueurs dans cet ordre.
- Popup par marqueur : nom du lieu, et pour les étapes, dates d'arrivée/départ (`date_arrivee`/`date_depart` déjà présentes dans `EtapeItineraire`).
- Cadrage automatique (`fitBounds`) pour englober tous les points affichés.

**Placement :** au-dessus de la liste ordonnée `<ol>` déjà existante dans `PlanifierTab.tsx` — la liste texte reste en dessous pour le détail jours/dates, la carte devient l'aperçu visuel principal.

**Repli si coordonnées manquantes :** si le départ, l'arrivée, ou une étape retenue a `lat`/`lon` à `None`, la carte ne s'affiche pas — un message discret (« Carte indisponible pour cet itinéraire ») la remplace. La liste texte, elle, reste toujours affichée indépendamment de la disponibilité des coordonnées. Pas de carte partielle avec des points manquants.

## 4. Tests

**Backend :**
- Chargement de la table IATA → coordonnées : lookup correct pour un code connu, `None` (pas d'exception) pour un code absent.
- Intégration `/voyage/planifier` : `lat`/`lon` présents dans la réponse pour un cas complet (départ/étape/arrivée tous dans la table) ; `None` pour un IATA absent de la table (table mockée en test, pas besoin du vrai CSV).

**Frontend :** `react-leaflet` est difficile à exercer tel quel en JSDOM (canvas/DOM réels absents) — les composants `MapContainer`/`Marker`/`Polyline`/`Popup` sont mockés dans le test (même pattern déjà utilisé dans ce repo pour framer-motion), pour tester la logique pure du composant :
- Le nombre de marqueurs rendus correspond au nombre de points de l'itinéraire (départ + étapes + arrivée).
- Le repli « carte indisponible » s'affiche quand un point a des coordonnées manquantes.

Pas de test visuel du rendu Leaflet réel — vérifié manuellement en lançant le dev server sur un itinéraire planifié.

## 5. Intégration technique

Conventions existantes respectées :
- `backend/app/services/voyage/data/airports_iata.csv` (nouvelle donnée statique) + un petit loader (ex. `airports.py`, fonction `lookup_coords(iata: str) -> tuple[float, float] | None`)
- `backend/app/api/voyage/schemas.py` : `PointItineraire`, extension de `EtapeItineraire`/`ItineraireOut`
- `backend/app/api/voyage/routes.py` : enrichissement dans `post_planifier`, aucun autre endpoint touché
- `frontend/components/voyage/ItineraryMap.tsx` (nouveau) + intégration dans `PlanifierTab.tsx`
- `frontend/lib/voyage.ts` : extension des types `EtapeItineraire`/`Itineraire`
- Nouvelles dépendances npm : `leaflet`, `react-leaflet`, `@types/leaflet`

## Limites connues (v1)

- Pas de sélection/interaction sur la carte (clic marqueur → liste, etc.) — visualisation seule.
- Pas d'affichage des lieux de la wishlist non retenus par le solveur.
- Pas de transport terrestre représenté — uniquement les points aériens, comme le reste du module Voyage (cf. spec du planificateur).
- La table IATA → coordonnées est un instantané figé au moment de sa génération (aéroports nouveaux/fermés après cette date non reflétés) — acceptable pour un usage personnel, pas de mécanisme de mise à jour automatique prévu en v1.

## Décomposition

1. Table IATA → coordonnées (CSV + loader) + tests.
2. Backend : enrichissement `lat`/`lon` dans la réponse `/planifier` (schémas + route) + tests.
3. Frontend : types étendus + `ItineraryMap.tsx` + intégration dans `PlanifierTab.tsx` + tests (mocks Leaflet).

Sous-projet petit et ciblé (une seule dépendance externe nouvelle, aucun changement au solveur ni au client Duffel) — adapté à un plan d'implémentation unique.
