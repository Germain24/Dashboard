# Mission Control — Plan d'orchestration

> **Document de référence.** Ce fichier décrit l'état du projet, la stack cible,
> et le découpage en conversations indépendantes. À copier-coller au début de
> chaque nouvelle conversation, ou à référencer via son chemin absolu.

## Vision

Créer un robot personnel qui tourne en local sur le PC de Germain : dashboard
de vie pour suivre finance long terme (analyse Buffett mensuelle, rebalancing
trimestriel manuel), nutrition (prise de muscle), garde-robe, agenda, études,
entraînement, budget, cuisine, habitudes et livres. Accessible via un site
web (local + accès distant sécurisé). Agent IA conversationnel intégré.

## Stack effective (post-CONV 1)

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.13
- **Python** : ≥ 3.10, gestionnaire `uv`
- **DB** : SQLite (`data/mission-control.db`)
- **Frontend** : Next.js 15.5 + React 19.1 + TailwindCSS 4 + TypeScript 5
- **UI** : style shadcn/ui (composants maison + CSS variables)
- **Imports xlsx** : `python-calamine` (tolérant aux fichiers corrompus)
- **Agent IA** : Anthropic Claude API (tool calling natif), abstraction pour
  permettre Ollama en local plus tard
- **Scheduler** : APScheduler intégré au backend FastAPI
- **Auth** : Tailscale pour l'accès distant (V1), NextAuth.js si besoin
  d'auth applicative ultérieure
- **Tests** : pytest + Vitest/Playwright côté front

## État actuel (snapshot 2026-05-14, post CONV 1)

Repo `mission-control/` opérationnel. Fondation FastAPI + Next.js + SQLite en
place, 17 tables créées, 4 098 lignes legacy importées. `make dev` répond, les
11 pages des modules sont routées (vides). Voir `CONV1_DONE.md` pour les
détails.

Le code Streamlit historique reste disponible en lecture seule dans
`openclaw/mon_espace/` (à garder pendant la phase 2 comme référence métier
pour les portages, puis suppressible).

| Module      | Code Streamlit (référence) | DB peuplée par CONV 1                                       | Migration |
|-------------|-----------------------------|-------------------------------------------------------------|-----------|
| Finance     | ✅ porté + Buffett refacto  | `snapshot_portefeuille`, `buffett_run` (nouvelle), `buffett_run_result` (renommée), `transaction`, `position` | **Fait** |
| Garde-robe  | 641 lignes                  | `vetement` (23), `tenue_history` (1)                        | CONV 2    |
| Santé       | ✅ porté (CONV 3)           | `mesure_sante` (+photo/note), `plan_nutrition` (+5 cols), `aliment`, `nutrition_goal` (nouvelle) | **Fait** |
| Agenda      | ✅ porté (CONV 5)           | `evenement` (étendu), `regle_recurrence` (nouvelle), `tache` (nouvelle) | **Fait** |
| Études      | ✅ from-scratch (CONV 6)    | `cours`, `evaluation`, `session_etude` (table `etude` stub supprimée) | **Fait** |
| Entraînement| ✅ porté (CONV 7) + Garmin  | `seance` (étendue), `exercice` (33+23), `programme`, `programme_jour`, `set_serie`, `course_cardio` | **Fait** |
| Budget      | Inexistant                  | tables vides                                                | CONV 8    |
| Cuisine     | Inexistant                  | tables vides                                                | CONV 9    |
| Habitudes   | Inexistant                  | tables vides                                                | CONV 10   |
| Livres      | Inexistant                  | tables vides                                                | CONV 11   |

## Phases & conversations

L'ordre suit les dépendances. CONV 1 doit être faite avant tout le reste.

### Phase 1 — Fondation

| #     | Titre                                          | Statut                       |
|-------|------------------------------------------------|------------------------------|
| CONV 1| Extraction + bootstrap monorepo + SQLite       | **✅ Terminée 2026-05-14**   |

### Phase 2 — Port des modules existants

| #     | Titre                                          | Statut  |
|-------|------------------------------------------------|---------|
| CONV 2| Module Garde-robe                              | **✅ Terminée 2026-05-16** (CONV2_DONE.md à fournir, commit Git à faire) |
| CONV 3| Module Santé / Nutrition                       | **✅ Terminée 2026-05-17** (commit `ac38f21`) |
| CONV 4| Module Finance (suivi + Buffett mensuel)       | **✅ Terminée 2026-05-28** (commit `81ed30c`, 40 tests, Phase 2 = 100%) |
| CONV 5| Module Agenda (vrai)                           | **✅ Terminée 2026-05-25** (commit `63fc207`, boucle CONV 7 fermée) |
| CONV 6| Module Études                                  | **✅ Terminée 2026-05-26** (43 tests verts, **commit Git à faire**) |

### Phase 3 — Nouveaux modules de vie

| #      | Titre                                         | Statut  |
|--------|-----------------------------------------------|---------|
| CONV 7 | Module Entraînement (sport, prise de muscle)  | **✅ Terminée 2026-05-20** (148 tests verts, Garmin importé) |
| CONV 8 | Module Budget (dépenses personnelles)         | À faire |
| CONV 9 | Module Cuisine (recettes & meal planning)     | À faire |
| CONV 10| Module Habitudes (habit tracker)              | À faire |
| CONV 11| Module Livres                                 | À faire |

### Conversations transverses

| #          | Titre                                          | Statut  |
|------------|------------------------------------------------|---------|
| CONV DESIGN| Design system + migration UI existante         | **✅ Terminée 2026-05-26** (commits `cb87444`, `583a7cf`, `39d951e`, `59d158e`) |

**Design system livré, contrat strict pour toutes les CONV à venir** :
- `frontend/DESIGN.md` = spec de référence (mood Minimal Mono, accent bleu,
  thème follow-system, densité compact, system-ui)
- `frontend/components/ui/` contient 12 primitives à utiliser systématiquement
  (Button, Badge, Card, Input, Textarea, Select, Tabs, Spinner, Skeleton,
  EmptyState, ChartFrame, Dialog) — ne **pas** réimplémenter inline
- Pas de classes Tailwind hardcoded avec couleurs absolues (`text-gray-400`,
  `bg-blue-600`, etc.) — toujours via CSS variables (`var(--muted)`,
  `bg-accent`, etc.)
- Navigation mobile : `MobileNav` est en place dans `layout.tsx`
- Tester chaque nouveau module à 375 / 768 / 1280 / 1920 px

CONV 6 (Études) a été livrée AVANT le mode design ; faire une mini-passe de
rattrapage si des éléments de UI ne suivent pas les primitives (cf. les
modifications encore en suspens dans le worktree).

### Phase 4 — Couche intelligente & infra

| #      | Titre                                         | Statut  |
|--------|-----------------------------------------------|---------|
| CONV 12| Agent IA (chat + tool calling)                | À faire |
| CONV 13| Scheduler & jobs automatiques                 | À faire |
| CONV 14| Auth & accès distant (Tailscale)              | À faire |
| CONV 15| Tests, CI, documentation                      | À faire |

Chaque conversation a son brief détaillé dans
`orchestration/CONV<N>_<slug>.md`.

## Architecture cible

```
mission-control/
├── backend/                       # FastAPI + Python
│   ├── pyproject.toml             # géré par uv
│   ├── alembic.ini
│   ├── alembic/versions/          # migrations DB
│   ├── app/
│   │   ├── main.py                # FastAPI app
│   │   ├── core/                  # config, db, deps
│   │   ├── models/                # SQLModel
│   │   ├── api/                   # routers par module
│   │   ├── services/              # logique métier
│   │   └── agent/                 # CONV 12
│   ├── jobs/                      # CONV 13
│   └── tests/
├── frontend/                      # Next.js 15
│   ├── package.json
│   ├── app/                       # App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx               # Dashboard global
│   │   ├── finance/
│   │   ├── garderobe/
│   │   ├── sante/
│   │   ├── agenda/
│   │   ├── etudes/
│   │   ├── entrainement/
│   │   ├── budget/
│   │   ├── cuisine/
│   │   ├── habitudes/
│   │   ├── livres/
│   │   └── robot/                 # chat agent
│   ├── components/                # shadcn/ui (maison)
│   └── lib/                       # API client, utils
├── data/
│   ├── mission-control.db         # SQLite
│   └── imports/                   # CSV brokers, .ics, etc.
├── orchestration/                 # suivi projet — seul dossier de gestion
│   ├── PLAN.md                    # ce fichier — document de référence
│   ├── CHANGELOG.md               # historique chronologique des features
│   ├── graphify/                  # knowledge graph (graphify query/path/explain)
│   │   ├── graph.json
│   │   ├── GRAPH_REPORT.md
│   │   └── graph.html
│   ├── convs/
│   │   ├── done/                  # rapports de fin de CONV (CONV*_DONE.md)
│   │   └── briefs/                # briefs de CONV (passées + futures)
│   └── logs/
│       └── ACTIVITY.md            # journal d'activité Claude
├── docker-compose.yml             # backend + frontend dev (optionnel)
├── Makefile                       # make dev, make test...
└── README.md
```

## Notes héritées des CONV terminées (à respecter dans toutes les CONV suivantes)

### Issues de CONV 1

1. **Pydantic 2.13 + SQLModel 0.0.38 : un champ nommé `date` clash avec
   `datetime.date`.** Workaround : `import datetime as dt` et utiliser
   `dt.date`. À respecter dans tous les modèles à venir.
2. **`python-calamine`** est le lecteur xlsx privilégié (résiste aux fichiers
   légèrement corrompus). Pas `openpyxl` par défaut.
3. **`ToutBroker.xlsx` n'est pas un journal de transactions** — c'est la
   **sortie d'une analyse Buffett précédente** (1741 actions scorées MOAT),
   importée temporairement dans la table `watchlist_entry`. La table sera
   renommée `buffett_run_result` lors de CONV 4 pour refléter sa vraie nature.
4. **Workflow Buffett — 3 cadences distinctes** :
   - `tickers.csv` = univers d'analyse (à terme tout l'univers monde,
     ~50k stocks visés).
   - `WarrenBuffetMensuel.py` = analyse fondamentale + optimisation, **tourne
     1×/mois en batch nocturne** (plusieurs heures, géré par CONV 13 scheduler).
     Sortie persistée en tables `buffett_run` + `buffett_run_result`.
   - **Rebalancing trimestriel = action humaine** : Germain compare son
     portefeuille réel à la dernière allocation cible, décide quoi acheter/
     vendre. CONV 4 fournit le diff visuel, jamais d'exécution automatique.
5. **Snapshot portefeuille quotidien** : ce job (CONV 13) est ce qui va
   alimenter `snapshot_portefeuille` après l'import initial — il faut donc
   l'activer avant que les données ne deviennent stales.
6. **Code legacy de référence** : tant que les CONV 2 à 6 ne sont pas faites,
   garder `openclaw/mon_espace/{habits,sante,finance,agenda}/` accessible
   en lecture seule. Une fois la Phase 2 complète, suppression OK.
7. **Schéma DB de CONV 1** : 17 tables au total. Voir `CONV1_DONE.md` pour
   le détail. Les tables vides seront peuplées par les CONV correspondantes.

### Issues de CONV 3

8. **Sandbox Linux + Git Windows** : le sandbox d'exécution ne peut pas écrire
   directement dans `.git/index` (lock file Windows). Contournement à utiliser
   pour les commits depuis CONV 4+ :
   `GIT_INDEX_FILE=/tmp/git_index_xxx git add <fichiers>` puis commit. À garder
   en tête si une CONV bloque sur un `git add`.
9. **Tool `Write` tronque les fichiers Python > ~200 lignes.** Contournement :
   passer par `cat > file << 'EOF' ... EOF` en bash pour les fichiers critiques.
   **Recommandation forte pour toutes les CONV** : structurer le code en
   sous-modules de **< 200 lignes** chacun. C'est aussi mieux pour la lisibilité.
10. **Imports pandas/scipy lazy.** CONV 3 a démontré qu'isoler la logique pure
    (sans pandas/scipy) dans un sous-module dédié rend les tests <1 s même
    sans la stack scientifique installée. Patron à reproduire en CONV 4
    (séparer `scoring` pur Python du reste qui charge yfinance/scipy).
11. **Hook d'intensité Santé ↔ Entraînement** : ✅ livré en CONV 7. Santé
    appelle `compute_intensity_for_date()` via **import in-process**
    (`from app.services.entrainement import ...`) avec `try/except` + fallback
    `default_intensity_for_date()`. Pas de round-trip HTTP — c'est plus rapide
    et plus robuste vu qu'on est dans la même app FastAPI.

### Issues de CONV 7

12. **Mount FUSE Windows ↔ Linux désynchronisé** : le tool `Write` peut tronquer
    silencieusement un fichier Python côté sandbox Linux (15 lignes au lieu de
    50) alors qu'il est complet côté Windows. Pire : après une `Edit` Windows,
    `grep` voit la nouvelle version mais l'AST que Python compile peut rester
    l'ancien. **Workaround systématique** pour tout fichier Python critique :
    réécriture finale via `cat > file << 'EOF' ... EOF` en bash. À garder en
    tête dès CONV 4 (gros refactor Buffett, beaucoup de fichiers).
13. **Race condition sur les seeds idempotents** (révélée par React Strict Mode
    + Next.js dev qui double-déclenche les GET au mount). Si deux requêtes
    parallèles voient la table vide et tentent d'insérer le même seed, l'une
    plante en `UNIQUE constraint failed`. **Tout helper de seed/upsert
    idempotent doit** : attraper `IntegrityError`, faire `session.rollback()`,
    et retourner l'enregistrement existant. À vérifier dans CONV 4 (seed des
    tickers Buffett notamment).
14. **Intégration inter-modules = import in-process**, pas HTTP. Le contrat
    Santé↔Entraînement parlait d'« appel HTTP/import » ; on a tranché pour
    l'import direct (try/except + fallback). Patron à reproduire pour toutes
    les futures intégrations (Études → Agenda, Cuisine → Santé, Habitudes →
    Entraînement, etc.) tant qu'on reste mono-process FastAPI.
15. **Ordre des routes FastAPI** : `/intensity/today` doit être déclarée
    AVANT `/intensity/{date}` sinon `today` est capturé comme paramètre.
    Vérifier dans tous les routers qui ont des routes "spéciales" + des
    routes paramétrées.
16. **Pas de cascade FK en SQLite** : suppression d'un parent ne supprime pas
    les enfants automatiquement. Faire la suppression manuelle en service
    (ex. `delete_session` supprime ses `SetSerie`). Critique pour CONV 4 où
    `transaction` aura des références multiples.

### Issues de CONV 5

17. **Récurrences = occurrences virtuelles, jamais persistées.** `RegleRecurrence`
    stocke un format JSON simple (`weekdays: [0,2,4]`, `start_time`, `end_time`,
    `until`) et `expand_rules_for_window` génère les occurrences à la volée.
    Avantage : supprimer "ce jeudi seulement" = front ignore une date, aucune
    écriture DB. Coût : si tu veux des exceptions persistantes (EXDATE), il
    faudra une table dédiée en V2.
18. **Contrat Études → Agenda déjà câblé**. Table `tache` a `source` et
    `source_id` ; CONV 6 doit créer ses entrées de devoirs avec
    `source="etudes"` + `source_id=<id_evaluation>`. **À respecter strictement
    sans changer le schéma.**
19. **`Evenement.updated_at` n'existe pas** (omission de CONV 1). `Tache` et
    `RegleRecurrence` l'ont mais pas `Evenement`. Si une CONV future doit
    auditer les modifs d'événements, ajouter via une nouvelle migration —
    pas urgent.
20. **Bridge inter-modules silencieux par défaut.** `entrainement_bridge.py`
    capture toute exception et retourne `None` plutôt que de propager. C'est
    le bon patron pour les intégrations optionnelles : un module en panne ne
    bloque pas le module appelant. À reproduire pour Études → Agenda
    (création de tâche depuis évaluation).

### Issues de CONV 6

21. **Signature réelle du bridge Agenda** : `agenda.tasks.create_task(session,
    dict)` (pas `create_tache(session, TacheCreate(...))` comme indiqué dans
    le brief CONV 6 — le brief était en avance sur l'implémentation CONV 5).
    À retenir pour les futures intégrations vers Agenda.
22. **`Cours.note_finale` = source de vérité GPA.** Le calcul GPA ne dépend
    PAS de la table `evaluation` — celle-ci ne stocke que les deadlines.
    Cela permet à `grades.py` d'être 100% pur Python, testable sans DB
    (cf. pattern note 10).
23. **Stub `etude` supprimé.** La table `etude` créée vide en CONV 1 a été
    droppée par la migration `d4e5f6a7b8c9`. Si une CONV future veut un
    autre concept "étude" (ex. sessions à long terme), nouvelle migration
    et nouveau nom de table — ne pas réutiliser `etude`.

### Issues de CONV DESIGN

24. **Design system contraignant pour les CONV futures** : utiliser
    obligatoirement les primitives de `frontend/components/ui/`, jamais
    réimplémenter inline. Voir aussi `frontend/DESIGN.md` pour les patterns
    d'écran complets.
25. **Pas de couleurs Tailwind hardcoded** (`text-gray-XXX`, `bg-blue-XXX`,
    etc.). Toujours via CSS variables (`var(--muted)`, `bg-accent`,
    `text-foreground`, etc.) qui s'adaptent au theme dark/light.
26. **Pattern client/server Next.js** : `MobileNav` est un client component
    importé depuis un server layout — c'est valide et c'est le patron à
    utiliser pour toute interactivité mineure dans `layout.tsx`.
27. **`Dialog` mobile-aware** : la primitive devient un bottom-sheet en
    mobile et un modal en desktop. À utiliser pour tout flow de saisie
    long ou détaillé.
28. **Mobile-first systématique** : tester chaque nouvelle UI à 375 / 768 /
    1280 / 1920 px avant de fermer une CONV. La sidebar disparaît en mobile,
    `MobileNav` la remplace via hamburger.

### Issues de CONV 4

29. **Renommage `watchlist_entry` → `buffett_run_result`** appliqué. Les
    1741 lignes héritées de CONV 1 sont conservées avec `run_id = NULL` ;
    le rebalancing filtre implicitement les runs terminés (`run_id IS NOT
    NULL`). Si tu lances un nouveau run Buffett, les résultats arrivent
    en cascade dans la table avec `run_id = <nouvelle_id>`.
30. **`SnapshotPortefeuille` utilise `.valeur` et `.investit`** (pas
    `.valeur_totale` / `.montant_investi`), `Transaction` utilise `.type`
    (pas `.type_transaction`) — noms de colonnes hérités de CONV 1. À garder
    en tête pour toute CONV future qui touche à Finance.
31. **APScheduler stubbé, pas activé.** Les jobs `job_daily_snapshot` (22h)
    et `job_monthly_buffett` (1er du mois 3h) sont définis dans
    `scheduler_stub.py` mais aucun scheduler tournant ne les exécute encore.
    **CONV 13 doit les activer** via `register_finance_jobs(scheduler)` dans
    le contexte global APScheduler.
32. **`scoring_pure.py` = patron à reproduire** pour tous les modules futurs
    qui ont du calcul lourd : logique pure Python, zéro dépendance pandas/
    scipy, testable en < 1 s. Le wrapper `scoring.py` charge pandas pour le
    runtime. Pattern parfait pour Habitudes (calcul streaks), Cuisine
    (optim plan repas), Budget (catégorisation).
33. **Pydantic v2 partout** : `class Config` est déprécié, utiliser
    `model_config = ConfigDict(...)`. Aligné dans CONV 4.

## Règles transverses

1. **Données réelles jamais commitées.** `data/` est gitignored sauf
   `data/imports/.gitkeep`. Sauvegardes via SQLite backup file (CONV 13).
2. **Schémas SQLModel = source de vérité.** Toute donnée passe par SQLModel.
   Plus de JSON brut éparpillé.
3. **API contract first.** Endpoints FastAPI documentés via OpenAPI auto-gen,
   le frontend Next.js génère son client TypeScript depuis ce schéma.
4. **Pas de logique métier dans Next.js.** Le frontend appelle l'API et
   affiche. Toute optimisation, calcul, validation = backend.
5. **Pas de secrets en clair.** `.env` gitignored, exemple dans `.env.example`.
6. **Timezone unique** : `America/Montreal`. Locale unique : `fr-CA`. Définies
   dans `core/config.py`.
7. **Versions pinnées.** `pyproject.toml` pour Python, lockfile à jour côté
   front.
8. **Tests obligatoires sur la logique critique** : calculs nutrition, scoring
   Buffett, score thermique garde-robe, optimiseur. Front : tests E2E sur les
   flows critiques.

## Comment je travaille (orchestrateur)

Cette conversation **ne touche pas au code**. Mon rôle :

- Maintenir ce PLAN.md à jour quand l'une des CONV se termine.
- Mettre à jour le statut dans les tables de phases.
- Rédiger / ajuster les briefs des CONV.
- Arbitrer les décisions transverses qui touchent plusieurs modules.
- Reformuler en prompt clair tout ce que tu veux confier à une autre conversation.

Pour me notifier qu'une CONV est terminée, copie-moi le récap final de l'autre
Claude (ou uploade le fichier `CONVN_DONE.md`) et je mets à jour ce document.
