# Design — Remise à niveau complète du dashboard (audit 2026-06-10)

Validé par Germain le 2026-06-10.

## Contexte

Audit du code au 2026-06-10 (branche `feat/ameliorations-section-e`, vague 1 des
améliorations 1–200 terminée, vague 2 entamée au seul item #202) :

- **Films et Séries sont des placeholders** : `frontend/src/app/film/page.tsx` et
  `series/page.tsx` rendent `ModulePlaceholder`. Aucun backend. Seuls modules
  inexistants sur 17.
- **Patterns vague 1 jamais généralisés** : repository (#6), pagination (#8),
  tri/filtres (#9), TanStack Query (#16), error boundaries (#21) appliqués
  uniquement à `finance/transactions` « en référence ». `frontend/lib/queries/`
  ne contient que `finance.ts` ; 11 repositories backend créés, un seul câblé.
- **Tests frontend quasi absents** : 115 fichiers de tests backend vs 3 frontend.
- **`backend/app/api/` incohérent** : un package `finance/` propre vs 16 fichiers
  plats `routes_*.py` (jusqu'à 487 lignes), `schemas_*.py` pour 6 modules
  seulement.
- **Composants frontend trop gros** : `RecettesTab.tsx` 558 lignes,
  `AujourdhuiTab.tsx` 421, `BuffettTab.tsx` 391.
- Cycle d'import signalé par graphify sur `backend/app/main.py`.
- Vague 2 : items 236–255 (agents IA, chat vocal, coaching IA) contraires à la
  règle « pas d'IA conversationnelle dans le dashboard ».
- Pas de page Paramètres centralisée (config éparpillée dans `.env`).

## Approche retenue

**A — Fondations d'abord, par chantiers TDD.** Harmonisation backend →
généralisation frontend + tests → Films/Séries → réorganisation UI → vague 2
élaguée. Zéro double travail : les nouveaux modules sont construits sur les
patterns propres.

Workflow inchangé : 1 item = TDD = 1 commit = marquage `← FINIS ✓ (date)` dans
`orchestration/AMELIORATIONS_200.txt`. Les nouveaux items de ce design y sont
ajoutés en sections dédiées en fin de fichier. Vérification avant chaque
marquage : pytest + vitest + build.

## Chantier 1 — Harmonisation backend (~17 items, 1 par module)

Pour chaque module (agenda, budget, cuisine, data, entrainement, etudes,
garderobe, habitudes, journal, livres, musique, notifications, sante, scheduler,
skincare, health) :

- Passage au format du package `app/api/finance/` : dossier `app/api/<module>/`
  avec routes découpées si volumineuses et `schemas.py` extrait.
  **URLs inchangées** — zéro impact frontend, le contrat OpenAPI ne bouge pas.
- Repository câblé dans le service (les classes existent dans
  `app/repositories/`, seule finance est branchée).
- Pagination `limit/offset` + tri/filtres génériques (`app/core/pagination.py`,
  `app/core/query_params.py`) sur les routes de liste, rétro-compatible.
- Item transverse : corriger le cycle d'import `app/main.py`.

## Chantier 2 — Généralisation frontend (~16 items, 1 par module)

Pour chaque module restant :

- `lib/queries/<module>.ts` : hooks TanStack typés via `lib/schema.ts`
  (modèle : `lib/queries/finance.ts`), invalidation, migration des composants.
- Error boundary par module (modèle : finance).
- **Tests vitest livrés dans le même item** : hooks + composant principal.
  Le déficit de tests frontend se comble mécaniquement.
- Les composants > 400 lignes sont découpés à cette occasion (RecettesTab,
  AujourdhuiTab, BuffettTab, MoisTab…).

## Chantier 3 — Films + Séries (TMDB)

### Backend — domaine unique `films_series`

- Modèle `WatchItem` : `kind` (`film`|`serie`), `tmdb_id` (nullable — saisie
  manuelle possible), titre, affiche (URL), statut (`a_voir`|`en_cours`|`vu`|
  `abandonne`), note /10, dates (ajout, vu le), synopsis.
- Modèle `SerieProgress` : saison courante, épisode courant, lié au WatchItem.
- Migration Alembic.
- Service TMDB via httpx : clé en env (puis page Paramètres), cache TTL,
  **dégradation gracieuse** — sans clé ou hors-ligne, recherche TMDB désactivée
  mais CRUD manuel pleinement fonctionnel.
- Routes : recherche TMDB (`?q=`), CRUD watchlist, mise à jour progression
  série, stats (vus par an, temps total estimé).
- Repository + pagination + schemas dès la naissance (patterns chantier 1).

### Frontend

- Deux vraies pages remplaçant les placeholders, composants par module
  (`components/film/`, `components/series/`).
- Onglets : À voir / En cours / Vus.
- Recherche TMDB avec affiches, fiche détail avec synopsis.
- Séries : compteurs saison/épisode (suivi léger, pas de grille épisode par
  épisode).
- Hooks TanStack + tests vitest dès la naissance (patterns chantier 2).

## Chantier 4 — Réorganisation UI

- **Sidebar groupée par domaines** (remplace les 17 entrées plates),
  via `lib/modules.ts` :
  - *Quotidien* : Agenda, Habitudes, Journal, Garde-robe
  - *Corps* : Santé, Entraînement, Cuisine, Skincare
  - *Culture* : Livres, Films, Séries, Musique
  - *Argent* : Finance, Budget
  - *Travail* : Études (le module Documents le rejoindra)
  - *Système* : Données, Jobs planifiés, Paramètres
- **Page Paramètres centralisée** (nouvelle route `/parametres`) : clé TMDB,
  dossier musique, rétention backups, préférences UI. Backend : lecture/écriture
  d'un store de settings (les secrets restent en env, la page indique seulement
  leur présence).
- L'accueil conserve TodayPanel / CyclePlanner / DaySignals ; son enrichissement
  passe par les items vague 2 (Vue 360 #225, etc.).

## Chantier 5 — Vague 2 élaguée + nouveaux items

- **Élagage** : items 236–255 marqués `ABANDONNÉ ✗` (agents IA conversationnels,
  chat vocal, coaching IA — même décision que le module N). Les items
  statistiques purs restent : corrélations #221, prédictions par régression
  #228, heatmap #233 — ce sont des maths, pas de l'IA.
- **Nouveaux items** (sections dédiées en fin de fichier) :
  1. Recherche **dans les données** via la palette Cmd+K (aujourd'hui elle ne
     fait que naviguer) : transactions, recettes, livres, contacts agenda…
  2. **Ajout rapide global** depuis la palette : dépense, repas, séance, sans
     quitter la page courante.
  3. Module **Documents / Administratif** : échéances (CNI, passeport),
     contrats, garanties, avec rappels via le scheduler existant.
  4. Page **Paramètres** (détail au chantier 4).
- Le reste de la vague 2 est repris par impact décroissant : (***) d'abord.

## Gestion d'erreurs

- TMDB indisponible → toast + mode manuel, jamais bloquant.
- Refactors backend : contrat OpenAPI vérifié par `test_openapi_contract.py`,
  migrations contrôlées par `test_migrations.py`.
- Migrations frontend : l'ancien client `api()` reste fonctionnel pendant la
  transition, supprimé module par module.

## Tests

- TDD par item (workflow existant).
- Backend : pytest par module + contrats OpenAPI/migrations.
- Frontend : vitest (hooks + composant principal) livré avec chaque migration
  de module et chaque nouveau module.
- Build (`next build`) avant chaque marquage FINIS.

## Ordre d'exécution

1. Chantier 1 (backend) — fondation, risque faible, URLs stables.
2. Chantier 2 (frontend + tests) — consomme les routes harmonisées.
3. Chantier 3 (Films/Séries) — construit sur les patterns propres.
4. Chantier 4 (réorg UI + Paramètres).
5. Chantier 5 (vague 2 + nouveaux items) — fil long terme.
