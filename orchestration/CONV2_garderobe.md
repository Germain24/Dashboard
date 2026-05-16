# CONV 2 — Module Garde-robe

## Objectif

Porter le module `habits/` actuel (641 lignes Streamlit) vers la nouvelle stack
FastAPI + Next.js + SQLite. Renommer en "garderobe" (le nom "habits" prête à
confusion avec un futur module Habitudes).

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée** : repo `mission-control/` existe,
tables `Vetement` et `TenueHistory` créées et peuplées via import legacy.

## Code de référence (à porter, pas à conserver)

- `mon_espace/habits/logic.py` — 641 lignes, à éclater côté backend
- `mon_espace/habits/vetements.json` — déjà importé en SQLite en CONV 1
- `mon_espace/Dashboard.py` lignes 405-927 — UI Streamlit, à réécrire en
  React

## Décisions à prendre

1. **Pixel art** : tu gardes les assets PNG `habits/assets/`, ou tu passes
   aux emojis seulement pour simplifier ?
2. **Suggestion automatique** : déclenchée à l'ouverture de la page (comme
   aujourd'hui) ou via un bouton uniquement ?
3. **Body en coton** : règle de calcul thermique gardée à l'identique ?
4. **API météo** : OpenWeather (clé déjà dans `.env` ?) ou autre ?

## Fonctionnalités à porter

### Backend (`backend/app/services/garderobe/`)

- Calcul score thermique d'un item (par matière, layering)
- `suggest_outfit(temp_min, temp_max, wind, pluie)` — optimiseur
- `proprete_pct`, `vie_pct`, `needs_wash`, `is_worn_out`
- Score style + compatibilité couleurs (Old Money palette)
- `get_purchase_recommendations` — analyse des manques
- `get_weather()` — appel OpenWeather pour Montréal

### Endpoints FastAPI

```
GET    /api/garderobe/vetements         # liste, filtres
POST   /api/garderobe/vetements         # ajouter
PATCH  /api/garderobe/vetements/{id}    # éditer
DELETE /api/garderobe/vetements/{id}

GET    /api/garderobe/meteo             # météo Montréal
POST   /api/garderobe/suggest           # suggestion tenue
POST   /api/garderobe/valider           # valider la tenue du jour
                                         # → incrémente portes, log history
GET    /api/garderobe/history           # historique tenues
GET    /api/garderobe/stats             # distribution couleurs, à laver
GET    /api/garderobe/recommendations   # achats suggérés
```

### Frontend (`frontend/app/garderobe/`)

- Page principale avec 5 onglets (Tenue du jour, Inventaire, Stats, Historique,
  Recommandations)
- Grille 6×2 des 12 slots (Manteau, Veste, Haut, Pantalon, Chaussures,
  Écharpe, Casquette, Lunettes, Bijoux ×2, Montre, Pendentif)
- Bandeau météo en haut
- Score thermique global avec indicateur visuel
- Bouton "Porter cette tenue" qui appelle `/valider`
- Filtres dynamiques dans Inventaire

## Hors-scope

- Nouvelles règles de suggestion (juste porter à l'identique)
- Photos réelles à la place du pixel art (V2)
- Achats trackés (lien avec module Budget — futur)

## Dépendances

- Prérequis : CONV 1.
- Synergique : CONV 8 (Budget) pourra plus tard tracker les achats vêtements.

## Suggestions techniques

- Côté front : React Server Components pour les vues read-only, Client
  Components avec `useSWR` pour les interactions (toggle body, navigation slots).
- Météo : cache 30 min côté backend pour ne pas spammer OpenWeather.
- Suggestion d'outfit : exposer en POST (pas GET) car ça modifie potentiellement
  l'état "suggested".

## Critères de succès

- [ ] Tous les vêtements importés visibles dans Inventaire
- [ ] Suggestion automatique fonctionne avec la météo réelle
- [ ] Validation d'une tenue persiste correctement (portes +1, history loggée)
- [ ] Stats identiques au Streamlit (à laver, couleurs)
- [ ] Recommandations d'achat fonctionnelles
- [ ] Mobile-friendly (grille s'adapte)

---

## Prompt d'amorce

```
Je veux porter le module Garde-robe de mon projet Mission Control vers la
nouvelle stack. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV2_garderobe.md
3. Pour la logique de référence : ancien code dans
   C:\Users\germa\Documents\GitHub\mission-control\legacy_code\habits\logic.py

Puis pose-moi les 4 questions de "Décisions à prendre" avant d'attaquer.
```
