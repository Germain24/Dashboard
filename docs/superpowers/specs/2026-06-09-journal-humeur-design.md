# Module Journal / Humeur (#476) — Design

Date : 2026-06-09
Statut : validé (brainstorming)
Périmètre : item #476 d'`orchestration/AMELIORATIONS_200.txt`, version **sans IA**.

## Contexte & objectif

Nouveau module de suivi d'**humeur quotidienne**, orienté **tendances et
corrélations** avec les autres modules. Aucune IA (cf. mémoire « pas d'IA ni
aides handicap ») : prompts éventuels = listes statiques, analyses = calculs
statistiques déterministes. Mono-utilisateur, local.

Décisions de cadrage :
- **Cœur** : suivi d'humeur d'abord (l'écriture libre est hors périmètre, itération future).
- **Cadence** : 1 entrée par jour (date unique).
- **Capturé** : humeur (1–5), énergie (1–5), tags d'émotions (multi), note courte optionnelle.
- **Corrélations** : sommeil, sport/entraînement, poids, dépenses.

Vérifié : aucun suivi d'humeur n'existe encore (Santé = nutrition/poids/sommeil ;
l'« Énergie » de Santé est la macro calorique, pas un niveau d'énergie). Ce module
est donc l'unique source d'humeur.

## Architecture

Suit le pattern module existant : `models/<m>.py` → `services/<m>/` →
`api/routes_<m>.py` → front `src/app/<m>/` + `components/<m>/` + `lib/<m>.ts` +
entrée `lib/modules.ts`.

### Modèle de données

Table `mood_entry` (`models/journal.py`) :

| champ | type | contrainte |
|---|---|---|
| id | int | PK |
| date | date | **unique** (1 entrée/jour) |
| humeur | int | 1–5 |
| energie | int | 1–5 |
| tags | str | JSON list de strings, défaut `"[]"` |
| note | str | défaut `""` |
| created_at | datetime | `utcnow` |
| updated_at | datetime | `utcnow`, maj à chaque upsert |

Migration Alembic dédiée (création de `mood_entry`).

Tags d'émotions : liste prédéfinie côté front (calme, heureux, motivé, fatigué,
anxieux, irrité, triste, serein, stressé, reconnaissant) + ajout libre. Stockés
tels quels dans `tags`.

### Services

`services/journal/mood.py` :
- `upsert_entry(session, date, humeur, energie, tags, note) -> MoodEntry`
  (crée ou met à jour l'entrée du jour ; valide 1 ≤ humeur/énergie ≤ 5).
- `get_entry(session, date)`, `list_entries(session, debut, fin)`, `delete_entry(session, date)`.
- `mood_trends(entries: list[dict]) -> dict` **pur** : moyenne mobile 7 j de
  l'humeur et de l'énergie, distribution des humeurs (compte par valeur 1–5),
  fréquence des tags (comptage décroissant), n entrées.

`services/journal/correlations.py` :
- `pearson(xs: list[float], ys: list[float]) -> float | None` **pur** : coefficient
  de Pearson ; `None` si < 2 paires ou variance nulle. Déterministe, testable.
- `interpret(r) -> dict` : force (`négligeable` |r|<0.2, `faible` <0.4,
  `modérée` <0.6, `forte` ≥0.6) + signe (`positif`/`négatif`).
- `compute_correlations(session, jours=90) -> dict` : construit des **séries
  journalières alignées par date** entre (humeur, énergie) et :
  - **sommeil** : heures de sommeil de la nuit (service Santé existant),
  - **sport** : 1 si une séance ce jour, sinon 0 (service Entraînement),
  - **poids** : poids du jour si mesuré (service Santé),
  - **dépenses** : somme des dépenses du jour (service Budget).
  Pour chaque paire, ne garder que les jours où **les deux** valeurs existent ;
  calculer `pearson`, renvoyer `{cible, r, force, signe, n}`. Inclure un
  avertissement `correlation_caveat: "corrélation ≠ causalité"`.
  Les accès aux autres modules passent par leurs services en **lecture seule** ;
  la fonction de calcul (alignement + pearson) est isolée et testée avec des
  sources injectées (pas de DB en test).

### API (`api/routes_journal.py`, préfixe `/journal`)

- `GET  /journal/entries?from&to` → liste d'entrées.
- `GET  /journal/entries/{date}` → entrée ou 404.
- `PUT  /journal/entries/{date}` (body : humeur, energie, tags, note) → upsert.
- `DELETE /journal/entries/{date}` → 204.
- `GET  /journal/trends?days=30` → sortie de `mood_trends`.
- `GET  /journal/correlations?days=90` → sortie de `compute_correlations`.

Enregistrement dans `api/__init__.py` (router) et `models/__init__.py` (import du modèle).

### Frontend

- `src/app/journal/page.tsx` (Server Component) → `<Journal/>` ; `loading.tsx` (PageSkeleton).
- `components/journal/` :
  - **QuickEntry** : saisie du jour — humeur 1–5 + énergie 1–5 (boutons/échelle),
    chips d'émotions (multi-select + ajout libre), note ; `PUT /journal/entries/{today}`.
  - **TrendsTab** : courbe humeur+énergie dans le temps (`ChartFrame`), heatmap
    calendrier (couleur par humeur), barres de fréquence des tags.
  - **CorrelationsPanel** : sommeil/sport/poids/dépenses avec r, force, signe, n,
    et l'avertissement corrélation ≠ causalité.
- `lib/journal.ts` : client `journalApi` + types (`MoodEntry`, `MoodTrends`, `Correlation`).
- `lib/modules.ts` : entrée `{ slug: "journal", label: "Journal", icon, group, ready: true }`.

## Flux de données

Saisie : QuickEntry → `PUT /journal/entries/{date}` → upsert `mood_entry`.
Tendances : TrendsTab → `GET /journal/trends` → `mood_trends(list_entries(...))`.
Corrélations : CorrelationsPanel → `GET /journal/correlations` → alignement
journalier (mood + sommeil/sport/poids/dépenses) → `pearson` par cible.

## Gestion d'erreurs

- Validation humeur/énergie ∈ [1,5] (422 sinon).
- `GET entries/{date}` inexistante → 404 ; `compute_correlations` avec trop peu
  de données → `r=None`, `n` faible, message « pas assez de données ».
- Sources de corrélation indisponibles/vides → la cible est simplement omise ou
  marquée `n=0`, jamais d'erreur 500.

## Tests (TDD)

Backend (pur, sans réseau/DB où possible) :
- `pearson` : valeurs connues (corrélation parfaite +1/−1, nulle, <2 points → None).
- `interpret` : seuils de force et signe.
- `compute_correlations` : alignement par date + omission des jours incomplets,
  via sources **injectées** (pas de DB).
- `mood_trends` : moyenne mobile, distribution, fréquence des tags, cas vide.
- `upsert_entry` : 1 entrée/jour (second PUT même date = update), bornes 1–5.
- Route smoke : `PUT` puis `GET` d'une entrée (TestClient).

Front : test util éventuel (formatage couleur humeur).

## Hors périmètre (YAGNI)

Écriture libre / journal textuel long, prompts guidés, plusieurs saisies par jour,
toute IA (génération, analyse de sentiment). Réservés à des itérations futures.
