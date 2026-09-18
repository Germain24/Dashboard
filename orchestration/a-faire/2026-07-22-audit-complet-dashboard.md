# Audit complet du dashboard — 8 segments

**Date** : 2026-07-22 · **Statut** : rédigé, exécution non commencée

Audit transversal du dépôt (backend + frontend + données + dépôt Git), conduit
segment par segment. Toutes les affirmations chiffrées de ce document sont
**mesurées**, pas estimées — la méthode et les commandes sont en annexe.

État du dépôt au moment de l'audit : branche `main`, dernier commit `48b482c`,
travail Finance non commité en cours (voir §3.A).

---

## Résumé exécutif — le constat central

Mission Control est un système **bien conçu et mal alimenté**. La qualité
d'ingénierie est réelle : couches propres, tokens de design respectés à 99 %,
fonctions pures testées, dégradation gracieuse des intégrations externes, zéro
`TODO`/`FIXME` dans 45 000 lignes de Python. Ce n'est pas là qu'est le problème.

Le problème est que **36 des 73 tables sont vides**, et la ligne de partage est
parfaitement nette :

| Se remplit tout seul | Lignes | | Demande un geste | Lignes |
|---|---:|---|---|---:|
| Buffett (jobs + yfinance) | 116 569 | | `set_serie` | 0 |
| Musique (scan + classification) | 1 418 | | `habit_entry` | 0 |
| Voyage — lieux (import) | 1 295 | | `recipe` | 0 |
| Budget (import Desjardins) | 887 | | `routine` | 0 |
| Agenda (iCal + Google Calendar) | 203 | | `skincare_log` | 0 |
| Finance transactions (import) | 432 | | `mood_entry`, `document`, `game`, `work_shift`, `cours`, `vocab_entry`… | 0 |

**Zéro exception dans les deux sens.** Toute amélioration qui suppose une saisie
manuelle est statistiquement condamnée d'avance ; toute amélioration qui
supprime une saisie a de bonnes chances de réussir. C'est le critère de
priorisation à appliquer à tout ce qui suit.

---

## Segment 1 — Socle & infrastructure

### 🔴 1.A Dépôt Git : 403 Mo, jamais compacté

```
count: 30653 objets libres    size: 403.18 MiB
in-pack: 0    packs: 0    ← aucun `git gc` n'a jamais tourné
```

**Cause racine** : `backend/data/financials_by_company/` contient **67 251
fichiers .xlsx / 1,0 Go** sur disque. Le dossier est bien dans `.gitignore`
(ligne 55) mais **6 155 de ces fichiers sont encore suivis** — `.gitignore` n'a
aucun effet sur ce qui est déjà indexé. `git status` en montre 6 modifiés :
chaque analyse Buffett réécrit des blobs binaires que Git stocke intégralement.

```bash
git rm -r --cached backend/data/financials_by_company/   # ~6 155 fichiers désindexés
git commit -m "chore: désindexe le cache xlsx (déjà gitignoré)"
git gc --prune=now                                        # 403 Mo → attendu ~30-60 Mo
```

> L'historique gardera les anciens blobs ; récupérer vraiment l'espace
> demanderait `git filter-repo`. À faire seulement si la taille du remote
> compte.

**Deux fichiers de 11 Mo non ignorés** polluent `git status` en permanence et
risquent le commit accidentel :

```
?? backend/data/cache_status.before_score_v2.20260719-183107.bak.json   (11,6 Mo)
?? backend/data/cache_status.json.bak-20260715-135731                   (11,2 Mo)
```

→ ajouter `backend/data/cache_status*.bak*` au `.gitignore`, puis supprimer.

### 🔴 1.B Données : deux bases, une table fantôme, de l'état runtime versionné

1. **`backend/data/mission-control.db` fait 0 octet.** La vraie base est
   `data/mission-control.db` (27 Mo). Une base vide au chemin « plausible » est
   un piège : un script lancé depuis `backend/` la prendra et affichera un
   dashboard vide sans erreur. → supprimer.
2. **Table de sauvegarde oubliée en base** :
   `buffett_run_result_bak_20260715_135731`, 10 471 lignes. → `DROP TABLE` +
   `VACUUM`.
3. **Fichiers d'état runtime suivis par Git**, qui changent à chaque exécution
   et salissent tous les diffs : `data/agenda_reminded.json`,
   `data/habitudes_reminded.json`.
4. **Données personnelles dans un dépôt que le `.gitignore` décrit lui-même
   comme public** : `data/mes_livres.json`, `data/app_settings.json`,
   `data/etudes_goal.json`, `data/entrainement_mesocycle.json`.
5. **Persistance éclatée** : 7 fichiers JSON hors SQLite portent de l'état
   métier (soldes de comptes, objectif d'études, mésocycle, rappels). Ils
   échappent aux migrations Alembic *et* au job de backup. S'ajoutera un CSV au
   segment 4.

### 🟠 1.C La surface produit est deux fois plus grande que l'usage

**36 des 73 tables sont vides** — routes, composants et endpoints existent
pourtant :

| Module | Tables vides |
|---|---|
| Routines / Automatisations | `routine`, `routine_run`, `tache`, `regle_recurrence` |
| Gaming | `game`, `game_goal` |
| Crédit | `credit_account`, `credit_score_entry`, `credit_action_rule` |
| Habitudes | `habit_entry` |
| Études | `cours`, `evaluation`, `session_etude` |
| Voyage | `voyage`, `voyage_etape`, `voyage_checklist_item` (mais 1 295 `lieu_voyage`) |
| Entraînement | `set_serie`, `course_cardio` (33 exercices définis, 0 série loggée) |
| Cuisine | `recipe`, `recipe_ingredient`, `shopping_list_item` |
| Films/Séries | `watch_item`, `serie_progress` |
| Livres | `book_note`, `book_quote`, `reading_session` (17 livres) |
| Journal / Skincare / Documents / Travail / Objectifs / Langues / Budget | `mood_entry`, `skincare_log`, `document`, `work_shift`, `life_goal`, `long_term_goal`, `vocab_entry`, `budget_envelope` |

**5 routes orphelines** (aucun lien depuis la nav) : `/bilan`, `/vue-360`,
`/snapshot` (atteignables seulement depuis `/score`), `/journal` (aucun lien
nulle part), `/habitudes` (uniquement via la palette de commandes).

### 🟠 1.D Tests & CI : le cœur du système n'est pas couvert

- **La suite backend complète n'a pas terminé en 45 min** (coupée à 55 %,
  498 s CPU, 1 961 tests collectés). Elle tape le réseau (yfinance/FX/GCal).
- **La CI ne joue que 8 chemins** : `test_health`, `test_cors`,
  `test_rate_limit`, `test_budget/`, `test_habitudes/`, `test_livres/`,
  `test_cuisine/`, `test_scheduler/`.
  → **Finance, Buffett (optimizer 1 579 lignes), Santé, Agenda, Entraînement,
  Garde-robe, Voyage, Études, Automatisations : zéro protection CI.** Les
  modules les plus complexes sont exactement ceux qui ne sont pas testés.

  Le correctif est à portée : `ARCHITECTURE.md` affirme déjà que les accès
  externes sont « confinés et injectables ». Il manque un marqueur
  `@pytest.mark.network` + `-m "not network"` en CI, pour passer de 8 à
  ~250 fichiers couverts.

- **Le ratchet de lint a calé.** `ruff-ci.toml` est une bonne idée mais la dette
  n'a pas bougé : 1 767 violations, dont ~40 seulement sont de vrais défauts (le
  reste est du style ou des faux positifs SQLAlchemy `== True`). Côté frontend,
  187 problèmes ESLint dont des classes réellement dangereuses :

| Occurrences | Règle | Pourquoi ça compte |
|---:|---|---|
| 21 | `react-hooks/set-state-in-effect` | double rendu, boucles potentielles (React 19) |
| 21 | `@typescript-eslint/no-misused-promises` | handler `async` là où `void` est attendu → rejets non catchés |
| 41 | `no-explicit-any` | érosion du typage généré depuis l'OpenAPI |
| ~30 | `jsx-a11y/*` | `<div onClick>` sans clavier — contredit PRODUCT.md |
| 6 | `no-floating-promises` | erreurs silencieusement avalées |

  Répartition par module : finance 30, budget 27, santé 20, films 17,
  entraînement 13, documents 8, habitudes 7.

- **`lib/types.ts` (15 210 lignes) a dérivé de l'OpenAPI** — le job CI le dit
  lui-même et reste `continue-on-error`.

### 🟠 1.E Performance mesurée (backend live)

| Endpoint | Temps | Poids | Problème |
|---|---:|---:|---|
| `/api/v1/musique/tracks` | **2,25 s** | 142 Ko | 1 418 pistes, aucune pagination |
| `/api/v1/budget/transactions` | **1,31 s** | 199 Ko | 887 lignes, signature sans `limit`/`offset` |
| `/openapi.json` | **13,3 s** | 362 Ko | routeurs montés 2× → 367 chemins, 469 opérations |
| `/api/v1/notifications` | 470 ms | 3,6 Ko | 1 419 lignes en table, jamais purgées |
| `/api/v1/garderobe/vetements` | 252 ms | 36 Ko | 900 octets par pièce pour 40 pièces |

`core/pagination.py` existe et est bien fait — **il n'est utilisé nulle part sur
les routes lourdes**. Idem `core/cache.py` : `ARCHITECTURE.md` le présente comme
le socle des « calculs finance coûteux », il n'y a que **2 usages**
(`api/finance/risk.py`, `services/finance/portfolio_state.py`).

### 🟡 1.F Dérive documentaire

- `backend/app/main.py` : description OpenAPI = « En CONV 1, seuls /health et les
  /ping de chaque module sont actifs » — c'est ce que voit `/docs` aujourd'hui,
  avec 469 opérations en ligne.
- `frontend/lib/api.ts` : même docstring périmée.
- `ARCHITECTURE.md` § Frontend : « persistance localStorage (offline/SWR) » —
  `QueryProvider.tsx` fait l'inverse et *supprime* la clé de cache legacy,
  volontairement (données privées). La doc décrit une décision annulée.

### 🟡 1.G Dépendances

`npm audit` : 1 vulnérabilité *moderate* transitive (`@opentelemetry/core` via
Next). Retards : **Next 15.5 → 16.2**, React 19.1 → 19.2, `lucide-react`
0.460 → 1.25, `sonner` 1.7 → 2.0, `vitest` 2.1 → 3.x, `eslint` 9 → 10.

---

## Segment 2 — Shell & design system

**Ce qui est solide** : discipline des tokens quasi parfaite — **2 couleurs en
dur** dans 167 composants. `MobileNav` a un vrai piège à focus + `Escape` +
verrou de scroll. `ModuleHeader` implémente le *roving tabindex* correctement.
`CommandPalette` dégrade proprement si l'API tombe. `ErrorBoundary` est câblé
dans les pages module. `lib/modules.ts` est réellement l'unique source de vérité
de la nav. `Finance` découpe ses 8 onglets en `next/dynamic`.

### 🔴 2.A Le kit `ui/` existe, mais 8 composants sur 10 l'ignorent

| Élément | Balise brute | Composant du kit | Adoption |
|---|---:|---:|---:|
| Bouton | 318 `<button>` | 68 `<Button>` | **18 %** |
| Champ texte | 159 `<input>` | 20 `<Input>` | **11 %** |
| Menu déroulant | 68 `<select>` | 2 `<Select>` | **3 %** |
| Tableau | 19 `<table>` | 1 `<DataTable>` | **5 %** |

`src/app/error.tsx` lui-même réécrit son bouton à la main. C'est la cause
directe des 30 violations `jsx-a11y` et de la dérive des états
`disabled`/`loading`/`focus`, en contradiction avec le principe de design n° 4
de PRODUCT.md (« un seul vocabulaire de boutons »).

**Ce n'est pas un chantier de réécriture globale** : figer la règle par le lint
(`react/forbid-elements` sur `button`/`select` hors de `components/ui/`), puis
convertir au fil de l'eau en commençant par les 5 fichiers les plus fautifs.

### 🟠 2.B L'onglet actif n'est jamais dans l'URL

Un seul fichier de tout le frontend utilise `useSearchParams`
(`voyage/PlanifierAutoTab.tsx`). Partout ailleurs l'onglet est un `useState`
local — ni URL, ni `localStorage`.

Conséquences quotidiennes : pas de lien profond (`/finance?tab=buffett`) ;
**Retour navigateur ne défait pas un changement d'onglet** (il quitte le
module) ; F5 renvoie à l'onglet par défaut ; la palette ne peut viser qu'un
module, jamais une vue ; impossible de mettre en favori « Finance › Impôts ».

Avec 26 modules à 4-8 onglets, c'est la friction la plus payante du frontend.
Correctif mécanique : un hook `useTabParam(defaut)` qui lit `?tab=` et fait
`router.replace(url, { scroll: false })`, branché dans `ModuleHeader`.

### 🟠 2.C Code mort dans le shell, propagé par un barrel

| Fichier | Lignes | Statut |
|---|---:|---|
| `components/layout/Deck.tsx` | 187 | Mort — l'accueil utilise `components/deck/Deck.tsx` |
| `components/layout/Sidebar.tsx` | 165 | Mort — remplacé par le Dock |
| `components/layout/PageLayout.tsx` | 31 | Mort — aucun consommateur |

**383 lignes**, toutes réexportées par `components/layout/index.ts`. Comme
~20 pages font `import { ModuleHeader } from '@/components/layout'`, elles
tirent Sidebar + Deck + NotificationsWidget dans leur graphe. Next tree-shake en
prod, mais ça alourdit la compilation en dev — et le commentaire de
`next.config.ts` cible exactement ce cas.

### 🟠 2.D La recherche globale couvre 3 modules sur 26 — dont un vide

`backend/app/api/search.py` interroge `BudgetTransaction`, `Recipe` et `Book`.
Or `recipe` a **0 ligne** : la recherche porte en pratique sur 887 transactions
et 17 livres. Elle ignore 1 418 pistes, 1 295 lieux, 203 événements,
68 aliments, 40 vêtements, les positions finance, les documents.

Deux défauts en plus :

- **Les résultats pointent vers la racine du module** (`href: "/budget"`),
  jamais vers l'élément trouvé.
- **Le montant est formaté `€` en dur** — `f"{t.montant:+.2f} €"` — alors que
  les 887 transactions ont `devise = 'CAD'` à 100 %. Un achat
  *SUPER C 26141 MONTREAL QC* s'affiche « −11.30 € ». (Le frontend Budget gère
  correctement CAD : 45 occurrences.)

### 🟠 2.E Le Deck : migration inachevée, et l'accueil coûte cher à parcourir

8 sections plein écran en scroll-snap. **Une seule** a une expérience conçue
(`Santé & Performance` → `CorpsExperience`) ; les 6 autres passent par
`GenericGroupExperience` — le docstring dit « le temps de leur migration ».

L'accueil est donc à 90 % un lanceur, et **seul le premier écran porte de
l'information réelle** (`TodayPanel`). Pour le « check-in rapide » revendiqué
par PRODUCT.md, c'est beaucoup de scroll pour peu de signal.

Deux directions à trancher : finir la migration (6 expériences dédiées, gros
chantier), ou **assumer l'inverse** — un seul écran d'accueil dense
(aujourd'hui + argent + corps) et laisser le Dock/palette faire le lanceur,
ce qu'ils font déjà très bien.

### 🟡 2.F Filet de secours inégal

- **22 `loading.tsx` sur 31 routes.** Sans : `bilan`, `donnees`, `gaming`,
  `langues`, `objectifs`, `score`, `travail`, `voyage`, `vue-360`.
- **1 seul `error.tsx`** (racine). Une erreur de rendu dans Musique remplace
  toute la page au lieu d'un message cadré dans le module.

### 🟡 2.G Détails

- **`<Freshness>` n'est branché que dans 2 fichiers**, alors que la moitié des
  données vient de jobs planifiés ou de sources externes (cours, météo, iCal,
  prix Super C). Le composant est écrit — il suffit de le poser.
- **`globals.css` : la règle `:focus-visible` est écrite trois fois à
  l'identique** (lignes 490, 630, 691). 800 lignes à scinder (tokens / base /
  deck / surcharges).
- `role="tablist"` sans `aria-controls`, et les corps d'onglets n'ont pas
  `role="tabpanel"` → les lecteurs d'écran n'associent pas onglet et panneau.

---

## Segment 3 — Finance / Buffett / Patrimoine / Crédit

Domaine le plus travaillé du dépôt (60 endpoints, 28 modules dans `buffett/`,
optimiseur de 1 579 lignes, copules de vine, DE multi-seed). Aussi celui qui
porte les risques les plus sérieux.

### 🔴 3.A Du code qui fait tourner la Finance n'est pas versionné

| Fichier | Lignes | État | Importé par |
|---|---:|---|---|
| `backend/app/services/finance/metrics.py` | 358 | **non suivi** | `portfolio.py`, `risk.py`, `snapshots.py` |
| `frontend/components/finance/JapanGoalWidget.tsx` | — | **non suivi** | `Finance.tsx` |
| `tests/test_finance/test_objectif_japon.py` | — | non suivi | — |
| `tests/test_finance/test_relative_valuation.py` | — | non suivi | — |
| `tests/test_finance/test_risk_concentration.py` | — | non suivi | — |

**Un `git clean -fd`, un clone neuf ou un changement de branche et le backend ne
démarre plus** : `ImportError` sur trois services Finance de premier plan.

S'y ajoutent **1 898 lignes ajoutées / 260 supprimées non commitées** sur
24 fichiers, tous au cœur du domaine :

```
scoring_pure.py  +375   snapshots.py  +230   risk.py  +218
transactions.py  +207   runner.py     +117   patrimoine.py  +93
account_history.py +85  portfolio.py   +77   finance-chart.ts +166
```

**À committer avant toute autre chose**, même en WIP sur une branche.

### 🔴 3.B Le test en échec — et pourquoi il ne testait rien

```
FAILED tests/test_finance/test_benchmark_injection.py::
       test_benchmark_deja_dans_l_univers_ne_reclame_aucune_injection
E  Failed: DID NOT RAISE any of (_Stop, RuntimeError)
```

Le test pose un coupe-circuit pour ne pas payer une optimisation complète :

```python
monkeypatch.setattr(opt, "load_etf_tickers", _boom, raising=False)
```

Mais `optimizer.py` importe le symbole **à l'intérieur** de la fonction :

```python
# optimizer.py:761
from .broker_availability import load_etf_tickers   # ré-importé à chaque appel
```

L'attribut posé sur le module n'est jamais lu. Le coupe-circuit ne se déclenche
pas, **le test lance un DE complet** — d'où 160 s pour 11 tests, et une
assertion qui échoue pour une raison sans rapport avec ce qu'elle prétend
vérifier.

**Ce n'est pas un cas isolé : `app/` contient 429 imports en portée locale, et
`tests/` 381 `monkeypatch.setattr`.** Chaque croisement des deux est un test qui
peut passer au vert sans rien exercer. C'est la cause la plus probable de la
lenteur de la suite (§1.D) — des tests censés court-circuiter qui exécutent le
pipeline réel.

Correctif de fond : importer en tête de module (ou patcher
`broker_availability.load_etf_tickers`, la source). Correctif de garde : un test
qui vérifie que le coupe-circuit s'est bien déclenché.

### 🟠 3.C 62 % des runs Buffett ne produisent aucun résultat

```
50 runs :  41 terminés · 8 erreur · 1 « en_cours » bloqué depuis le 2026-07-21
31 runs sur 50 n'ont AUCUNE ligne dans buffett_run_result
```

Deux familles d'erreurs :

1. **6 runs le 2026-07-12** — `Cours indisponibles (téléchargement des cours
   vide ou expiré)`. Incident de rate-limit Yahoo déjà traité (lissage à
   1 000 req/h).
2. **2 runs le 2026-07-20** — `Invalid value 'False' for dtype 'float64'`.
   Celui-là est **connu et contourné, pas corrigé** : le docstring de
   `_latest_optimizable_run` (`api/finance/buffett.py:795`) le nomme
   explicitement — « une incompatibilité pandas pendant la présélection ETF » —
   et la solution retenue est de réutiliser quand même le run en erreur.

**Le vrai problème : il est indiagnosticable après coup.** `reporting.py:162`
fait `run.erreur = erreur` avec un simple `str(e)` — la traceback n'est jamais
conservée. Un run planté la nuit ne laisse qu'une phrase.

Piste sérieuse pour le bug de type : dans le chemin de présélection ETF,
`_spearman_correlation` (`etf_selection.py:75`) fait

```python
values = np.asarray(returns[tickers], dtype=float)   # aucune garde
```

alors que sa voisine immédiate `_quality_scores` (l. 61) protège sa conversion
par un `try/except (TypeError, ValueError)`. C'est la seule coercition float non
gardée de ce chemin, et NumPy 2 lève exactement ce message quand un `False`
traîne dans la colonne. Correctif robuste :
`returns[tickers].apply(pd.to_numeric, errors="coerce")`.

**Priorité 1 sur ce point : persister la traceback** (`traceback.format_exc()`).
Sans ça, chaque prochain plantage repartira de zéro.

### 🟠 3.D Aucune rétention sur la plus grosse table du système

```
buffett_run_result                          116 569 lignes  (~90 % des 27 Mo de la base)
buffett_run_result_bak_20260715_135731       10 471 lignes  (sauvegarde oubliée)
```

Chaque run terminé conserve **l'univers scoré complet, ~10 450 lignes**,
indéfiniment. `config.py` définit pourtant `jobrun_retention_days = 30` et
`notification_retention_days = 30` — mais **rien pour les résultats Buffett**.

Proposition : garder l'intégralité pour les 3 derniers runs ; pour les plus
anciens, ne conserver que les lignes avec `allocation_pct is not null` (le
portefeuille retenu) + le top 100. Gain estimé : **−100 000 lignes, base ÷3**.

### 🟠 3.E Le centre de notifications est saturé de bruit

```
1 419 notifications · 0 lue · la plus ancienne date du 2026-06-17
dont 1 141 (80 %) « Job agenda_reminders terminé » / « 0 rappel(s) créé(s) »
```

Cause dans `services/scheduler/runner.py:17` — une notification est créée **à
chaque exécution réussie**, sans condition :

```python
result = func(session)
run.status = "success"
notif = Notification(source=job_id, titre=f"Job {job_id} terminé",
                     message=run.log, level="info")
```

Et la boucle se referme : la rétention ne supprime que les notifications
**lues**. Comme rien n'est jamais lu, **rien n'est jamais purgé** — la table
croît de ~40 lignes/jour pour toujours.

Un badge à 1 419 n'est pas une information : les 8 erreurs Buffett y sont
noyées. Correctif :

- ne notifier que sur `error`, ou quand le job renvoie un résultat réellement
  actionnable (convention : `None` = silencieux) ;
- la traçabilité de tous les runs est **déjà** couverte par `JobRun` et la page
  `/jobs` — la notification fait doublon ;
- purger aussi les notifications non lues au-delà de N jours.

Détail : deux conventions de nommage cohabitent pour la même source —
`agenda_reminders`/`agenda_reminder`, `habit_reminders`/`habit_reminder` —
reliquat d'un renommage incomplet.

### 🟡 3.F Patrimoine a deux portes d'entrée

`PatrimoineTab` est rendu **à la fois** par la route `/patrimoine` (module de
premier niveau) **et** par l'onglet « Patrimoine » de `/finance`. Même
composant, deux en-têtes différents. Il faut choisir.

À noter aussi la coexistence **€ (investissement) / CAD (budget)** entre
modules : cohérent avec la situation réelle, mais aucun écran ne l'explicite, et
`/api/search` s'y trompe déjà (§2.D).

### 🟡 3.G 49,5 Mo de résidus d'agents dans `backend/`

14 fichiers et 10 dossiers non suivis et non ignorés : `.codex-bf-etf-page.html`,
`.codex-bf-main.js`, `.codex-frankfurt-instruments.csv`,
`.codex-xetra-instruments.csv`, `.codex-verify-restart-20260722/`,
`.tmp-pytest-{starr,robust,history,opt,regime,turnover,eur,final,api,currency2}-*/`…
Plusieurs sont en permission refusée et font échouer `git status` en warnings.
→ `.gitignore` : `backend/.codex-*`, `backend/.tmp-pytest-*`, puis suppression.

### Ce qui marche bien

`/finance/portfolio` répond en 441 ms, `/buffett/runs` en 114 ms,
`/buffett/runs/{id}` est correctement borné (top 50 + allocations).
La gestion du run interrompu (`buffett_progress`) est prudente et bien
commentée — elle refuse explicitement de marquer « terminé » un DE tué en vol.
`returns_in_base_currency` dégrade proprement en devise native si le FX tombe.
Le problème n'est pas la qualité du code : c'est qu'il n'est ni commité, ni
couvert par la CI, ni observable quand il casse.

---

## Segment 4 — Corps (Santé, Cuisine, Entraînement, Skincare, Score)

**Carte d'usage réelle :**

| Table | Lignes | | Table | Lignes |
|---|---:|---|---|---:|
| `aliment` | 68 | | `set_serie` | **0** |
| `plan_nutrition` | 22 | | `course_cardio` | **0** |
| `meal_plan_entry` | 21 *(tous `recipe_id` NULL)* | | `recipe` / `recipe_ingredient` | **0** |
| `mesure_sante` | 12 | | `shopping_list_item` | **0** |
| `exercice` / `programme_jour` | 33 / 14 | | `skincare_log` | **0** |
| `seance` | 4 *(tous `exercices='null'`)* | | `skincare_product` | 6 |

### 🔴 4.A Le moteur d'entraînement le plus élaboré du dépôt tourne à vide

**2 120 lignes sur 18 modules** : `one_rm`, `progression`, `records`,
`muscle_volume`, `intensity`, `suggested_weight`, `mesocycle`, `correlation`,
`calories`, `garmin_seed`… Tout cet appareillage lit `set_serie` — **qui est
vide**. Les 4 séances enregistrées ont même `exercices = 'null'`.

Ce n'est pas un bug, c'est un problème de coût de saisie. Deux questions à
trancher avant d'écrire une ligne de code : combien de gestes faut-il aujourd'hui
pour logger « 3×8 @ 60 kg » ? Et logges-tu déjà ailleurs (il y a un
`garmin_seed.py`) ?

Si la réponse est « je logge sur ma montre », l'amélioration n'est pas un
meilleur formulaire — c'est **un import Garmin**, et 15 des 18 modules
deviennent utiles d'un coup.

### 🔴 4.B `mesure_sante.extra` est devenu un dépotoir JSON

La table poids/photos stocke des **sorties complètes de l'optimiseur nutrition**
dans sa colonne `extra` : macros consommées sur 40 nutriments + liste d'aliments
avec quantités et prix, plusieurs milliers de caractères par ligne.

C'est une duplication intégrale de `plan_nutrition`, qui possède pourtant les
colonnes prévues : `targets`, `quantites`, `consumed`, `totals`, `base_targets`,
`warning`. Résultat : deux sources de vérité, aucune contrainte, et une table
`mesure_sante` illisible pour ce à quoi elle sert.

### 🔴 4.C Les données santé sont incohérentes — et le Score s'en nourrit

```
poids :   52 kg (18/04) → 80 kg (20/04) → 80 kg (22/04) → 60 kg (22/05) → 55 kg (14/06)
kcal/j :  16 664  et  23 987     (cible calculée : 3 672)
```

Le poids varie de 28 kg en deux jours ; les calories « consommées » sont
manifestement des quantités multi-jours (batch cooking, courses hebdo)
enregistrées comme une journée.

Or `services/sante/score.py` calcule le score de forme quotidien à partir de
`MesureSante` (12 lignes), `Seance` (4) et `PlanNutrition` (22). **La page
`/score` affiche donc un indicateur bâti sur des valeurs aberrantes ou
absentes.**

Correctif : bornes de plausibilité à l'écriture (poids 40–150 kg, kcal/jour
800–6 000) et distinction explicite entre « quantité pour N jours » et
« consommé aujourd'hui ». Sans ça, tout le module Score est du bruit habillé en
signal.

### 🟠 4.D Cuisine est une coquille autour d'un moteur qui, lui, fonctionne

`shopping_list.py` (194 l) part de `MealPlanEntry` → `RecipeIngredient`. Avec
0 recette et 0 ingrédient, **la liste de courses ne peut structurellement rien
produire**, et les 21 entrées du planificateur de repas ont toutes
`recipe_id = NULL`.

Pendant ce temps, deux choses marchent : `store_pricing.py` (213 l) récupère les
prix Super C / Adonis, et `sante/optimizer.py` (382 l) produit chaque jour **une
liste d'aliments avec quantités précises et prix** — 22 plans générés du 04/04
au 17/07.

Le chemin court existe déjà : **dériver la liste de courses de la sortie de
l'optimiseur**, pas d'un modèle de recettes vide. Le modèle recettes peut rester
pour plus tard, mais il ne doit pas être sur le chemin critique.

**Quatrième couche de persistance** : l'inventaire du garde-manger est lu dans
la ligne `QuantiteDispo` de `aliments.csv`, pas en base.

### 🟠 4.E Skincare : 6 produits, 0 application enregistrée

7 endpoints, un `SkincareModule` dans le Deck, un job `skincare_reorder` qui a
tourné 6 fois. Aucun log. Même diagnostic que Habitudes : le coût de la coche
n'est pas payé.

### 🟡 4.F Constantes de score en dur

`SOMMEIL_CIBLE_H = 8.0` et `SPORT_CIBLE_SEMAINE = 4` sont figés dans
`score.py`, alors que `/parametres` se décrit comme « Variables constantes,
intégrations, rétention ».

### Ce qui marche

`sante/optimizer.py` est le vrai joyau du domaine — une optimisation
nutritionnelle sous contraintes sur 40 nutriments avec prix, qui tourne
réellement. `score.py` est proprement écrit (fonctions pures, `None` propagé
quand la donnée manque). Le scraping de prix fonctionne.

---

## Segment 5 — Exécution (Agenda, Automatisations, Habitudes, Objectifs, Jobs)

### 🟢 Agenda : le module le plus sain du dépôt

```
203 événements :  102 iCal · 59 Google Calendar · 39 planificateur · 2 manuels · 1 poubelles
```

80 % de la donnée arrive par synchronisation — **zéro friction de saisie**, et
c'est le seul module de la moitié « vie quotidienne » qui soit vraiment rempli.
Démonstration de la thèse générale : *ce qui se remplit tout seul se remplit ; ce
qui demande un geste ne se remplit pas.* Le planificateur automatique a produit
39 blocs : il fonctionne.

### 🔴 5.A Un job tourne 96×/jour pour ne rien faire, et sature tout le reste

```
agenda_reminders : cron minute="*/15"  →  963 exécutions en 30 jours
                   963 JobRun + 963 Notification « 0 rappel(s) créé(s) »
```

Les autres jobs tournent 6 à 43 fois sur la même période. À lui seul,
`agenda_reminders` représente **84 % des JobRun et 80 % des notifications**.

La fréquence de 15 min est légitime (rappeler un événement imminent). Ce qui ne
l'est pas, c'est de journaliser une notification à chaque passage à vide.
Combiné au correctif §3.E, le centre de notifications retombe de 1 419 à une
dizaine d'entrées réellement utiles.

### 🟠 5.B Le constructeur d'automatisations n'a jamais servi

`routine`, `routine_run`, `tache`, `regle_recurrence` : **0 ligne**. La page
`/routines` (803 lignes, la plus grosse page du frontend) propose un
constructeur no-code « SI … ALORS », un kill-switch global, des webhooks, un
ré-exécuteur avec rollback. Rien n'a jamais été créé.

En revanche, **les automatisations câblées en dur tournent** :
`anomaly_detection` (6×), `courses_check` (6×), `skincare_reorder` (6×),
`recap_soir` (14×), `daily_snapshot` (15×), `purge_old` (7×).

Le besoin est couvert par les jobs codés ; le constructeur générique est une
couche d'abstraction non utilisée. **C'est le meilleur candidat à la suppression
de tout le dépôt** — 803 lignes de frontend + une douzaine d'endpoints +
4 tables, pour zéro usage.

Ce qui est vraiment précieux dans `automatisations/`, ce sont les 26 services
d'analyse (`insights`, `correlations`, `causalites`, `forecast`, `wellbeing`,
`energy`, `heatmap`, `surcharge`) — mais ils sont enterrés dans `/routines`,
`/snapshot` et `/vue-360`, dont deux sont des **routes orphelines**. De
l'intelligence construite et payée qui n'atteint jamais l'écran.

### 🟠 5.C Habitudes : 6 habitudes définies, 0 coche depuis toujours

`habit` = 6 (Muscu, Course, Lecture, Sommeil ≥ 7 h, Pas de junk food,
Méditation), toutes actives. `habit_entry` = **0**. Le module a été retiré de la
nav (décision volontaire) mais la route `/habitudes` vit encore, atteignable
seulement par la palette, avec son backend, ses streaks et sa gamification.

Décision franche à prendre : supprimer, ou rendre le geste gratuit (une ligne de
cases à cocher dans le `TodayPanel`, là où le regard passe déjà chaque jour).

### 🟡 5.D Collision de noms sur « objectif »

`objectif_type` contient 55 lignes… qui sont des **objectifs de garde-robe**
(T-shirts ×15, Polos ×6, Chemises ×12, avec échelles de marques Uniqlo →
Visvim). Pendant ce temps le module `/objectifs` (« Masters, concours
gendarmerie, gestion d'actifs ») s'appuie sur `life_goal` et `long_term_goal` :
**0 ligne chacun**. À renommer (`garderobe_objectif_type`) avant que ça ne coûte
un bug.

---

## Segment 6 — Savoir & Culture (Études, Travail, Livres, Films/Séries, Musique, Gaming, Langues)

### 🟢 Musique : le module abouti

**1 418 pistes, 100 % classifiées**, 2 387 appartenances à des ambiances. Seul
module « culture » réellement vivant, et pour la même raison que l'Agenda : la
donnée arrive par un scan de dossier + classification automatique.

Seul défaut : `/musique/tracks` renvoie **142 Ko en 2,25 s** sans pagination.

### 🔴 6.A Cinq modules à zéro ligne

| Module | Tables | Lignes | Code en face |
|---|---|---:|---|
| **Études** | `cours`, `evaluation`, `session_etude` | 0 / 0 / 0 | 19 endpoints, `lib/etudes.ts` 328 l, 4 onglets |
| **Travail** | `work_shift` | 0 | 5 endpoints |
| **Gaming** | `game`, `game_goal` | 0 | 5 endpoints |
| **Langues** | `vocab_entry`, `projet_international` | 0 | 6 endpoints, `Langues.tsx` 327 l |
| **Films/Séries** | `watch_item`, `serie_progress` | 0 | 5 endpoints, `WatchlistSection.tsx` 368 l |

**Livres** est le cas intermédiaire : 17 livres, **tous au statut `a_lire`** —
aucun lu, aucun en cours, et `book_note`/`book_quote`/`reading_session` vides.
C'est une liste de souhaits, pas un suivi de lecture, alors que le module propose
notes, citations, sessions et un `BookDetailModal` de 283 lignes.

Ces cinq modules et demi représentent ~2 000 lignes de frontend et ~50 endpoints
qui n'affichent jamais rien d'autre qu'un état vide. Ils occupent la nav,
gonflent l'OpenAPI (13 s de génération), alourdissent les builds et diluent
l'attention.

Trois issues, à choisir module par module — « ne rien faire » n'en est pas une :

1. **Supprimer** (Gaming, Travail semblent les plus évidents)
2. **Alimenter automatiquement** (Films/Séries via TMDB + watchlist importée ;
   Études via l'iCal de cours **déjà synchronisé** — 102 événements iCal
   arrivent déjà)
3. **Réduire à l'essentiel** (Livres = une liste + un statut, on jette
   notes/citations/sessions)

### 🟠 6.B Films/Séries concentre les défauts d'accessibilité

17 problèmes ESLint dont 4 `click-events-have-key-events` et 4
`no-static-element-interactions` : les cartes de films sont des `<div onClick>`
non atteignables au clavier. Sur une grille de posters, c'est la manifestation
la plus visible du problème §2.A.

### 🟡 6.C Études pourrait se remplir tout seul

Le module attend cours, évaluations et sessions saisis à la main, alors que
l'agenda reçoit déjà **102 événements iCal**. Un rattachement
`Evenement → Cours` transformerait un module vide en module rempli sans un seul
geste de saisie.

---

## Segment 7 — Style & Horizons (Garde-robe, Voyage, Journal, Documents, Données, Paramètres)

### 🟢 Garde-robe : vivant et bien modélisé

40 pièces sur 10 catégories (Veste 11, Manteau 9, Haut 5, Pantalon 4…),
55 objectifs typés avec échelles de marques, historique de tenue, photos servies
via `/media/garderobe`, météo intégrée (`weather.py`, 352 l), import
d'inventaire (322 l). Tout ce qui a été livré récemment est en place.

Seule faiblesse mesurée : `/garderobe/vetements` renvoie **36 Ko pour 40
pièces** — 900 octets par vêtement, ce qui suggère qu'on sérialise tout pour une
vue liste.

### 🟠 7.A Voyage : 1 295 lieux, 0 voyage

`lieu_voyage` = 1 295 (Japon 67, États-Unis 15, Australie 14, Italie 12,
Chine 12) — la wishlist est massivement remplie. Mais `voyage`, `voyage_etape`,
`voyage_checklist_item` sont **vides** : le planificateur d'itinéraire
(`solver.py`, 335 l, 12 endpoints, carte Leaflet) n'a jamais servi.

Le remède est identifiable : le solveur devrait partir **directement de la
wishlist** (« fais-moi un itinéraire de 14 jours au Japon avec ces 67 lieux »)
plutôt que d'exiger de créer un voyage puis des étapes à la main.

### 🟠 7.B Journal : route orpheline et table vide

`mood_entry` = 0, et `/journal` **n'est référencé par aucun lien** de toute
l'application. Seul module strictement inatteignable sans taper l'URL. À
supprimer, ou à poser dans le `TodayPanel` (une ligne « humeur du jour »).

### 🟠 7.C Documents : 0 document, mais 8 problèmes de lint

Module « échéances, contrats, garanties, rappels » — `document` = 0. Et pourtant
`DocumentsTab.tsx` accumule 7 erreurs ESLint dont 2 `no-autofocus` et 2
`label-has-associated-control`. Du travail de finition sur un écran jamais
rempli.

### 🟡 7.D Données / Paramètres

`src/app/donnees/page.tsx` porte l'unique `react-hooks/set-state-in-effect` cité
en clair par ESLint :

```js
useEffect(() => {
  if (!table && tables[0]) setTable(tables[0])   // ← double rendu à chaque montage
}, [tables, table])
```

Et `/parametres` cumule 5 assertions de type inutiles. Ce sont les deux écrans
« système » — ceux dont on attend le plus de fiabilité.

---

## Backlog priorisé

### P0 — À faire en premier (≈ 1 h, risque de perte de données)

- [ ] **Committer le WIP Finance** — `metrics.py` et `JapanGoalWidget.tsx` ne
      sont pas versionnés et sont importés par du code actif : un `git clean`
      casse le backend *(§3.A)*
- [ ] `git rm -r --cached backend/data/financials_by_company/` +
      `git gc --prune=now` — dépôt 403 Mo → ~50 Mo *(§1.A)*
- [ ] `.gitignore` : `backend/.codex-*`, `backend/.tmp-pytest-*`,
      `backend/data/cache_status*.bak*`, `data/*_reminded.json` *(§1.A, §3.G)*
- [ ] Supprimer `backend/data/mission-control.db` (0 octet — piège de base vide)
      *(§1.B)*

### P1 — Cette semaine (impact quotidien immédiat)

- [ ] **`runner.py` : ne notifier que sur erreur** → badge 1 419 → ~10 *(5 min, §3.E)*
- [ ] **`useTabParam` dans `ModuleHeader`** → onglets dans l'URL, Retour
      navigateur, liens profonds *(1 h — meilleur ratio du frontend, §2.B)*
- [ ] **`traceback.format_exc()` dans `run.erreur`** → échecs Buffett
      diagnosticables *(10 min, §3.C)*
- [ ] **Marqueur `@pytest.mark.network` + `-m "not network"` en CI** → de 8 à
      ~250 fichiers de test couverts *(1 h, §1.D)*
- [ ] Pagination sur `/musique/tracks` et `/budget/transactions` → −2 s,
      −340 Ko *(30 min, §1.E)*
- [ ] Rétention `buffett_run_result` + `DROP TABLE …_bak` + purge notifications
      non lues → base ÷3 *(1 h, §3.D)*
- [ ] `search.py` : `devise` au lieu de `€`, liens vers l'élément, extension à
      Musique/Voyage/Agenda/Garde-robe *(1 h 30, §2.D)*
- [ ] Supprimer les 383 lignes mortes du shell + les retirer du barrel
      *(10 min, §2.C)*
- [ ] 9 `loading.tsx` manquants + dédupliquer les 3 règles `:focus-visible`
      *(25 min, §2.F, §2.G)*
- [ ] Corriger `_spearman_correlation` avec `pd.to_numeric(errors="coerce")` et
      l'import local de `load_etf_tickers` + réparer le test *(25 min, §3.B, §3.C)*
- [ ] Corriger les 3 docstrings périmées (`main.py`, `api.ts`,
      `ARCHITECTURE.md`) *(15 min, §1.F)*

### P2 — Décisions produit (à trancher avant de coder)

- [ ] **Que fait-on des 5 modules à zéro ligne** (Gaming, Travail, Langues,
      Films/Séries, Études) ? Recommandation : supprimer Gaming et Travail,
      alimenter Études depuis l'iCal déjà synchronisé, réduire Livres et
      Films/Séries à une liste + un statut *(§6.A)*
- [ ] **Supprimer le constructeur d'automatisations** (`/routines`, 803 lignes,
      4 tables vides) et **remonter à la place les 26 services d'analyse** —
      insights, corrélations, causalités, prévisions, surcharge — enterrés dans
      deux routes orphelines *(§5.B)*
- [ ] **Entraînement : import Garmin plutôt qu'un meilleur formulaire.**
      2 120 lignes de moteur attendent `set_serie` *(§4.A)*
- [ ] **Cuisine : dériver la liste de courses de l'optimiseur nutrition** (qui
      produit déjà aliments + quantités + prix) au lieu d'un modèle de recettes
      vide *(§4.D)*
- [ ] **Le Deck** : finir les 6 expériences manquantes, ou assumer un écran
      d'accueil dense unique et laisser le Dock faire le lanceur *(§2.E)*
- [ ] **Voyage** : faire partir le solveur d'itinéraire de la wishlist de
      1 295 lieux *(§7.A)*
- [ ] **Habitudes / Journal** : supprimer, ou poser dans le `TodayPanel`
      *(§5.C, §7.B)*
- [ ] **Patrimoine** : choisir entre la route `/patrimoine` et l'onglet Finance
      *(§3.F)*

### P3 — Dette de fond

- [ ] Bornes de plausibilité sur les données santé (poids, kcal) — le Score en
      dépend *(§4.C)*
- [ ] Sortir les blobs JSON de `mesure_sante.extra` vers `plan_nutrition` *(§4.B)*
- [ ] Ratchet de lint : les 21 `set-state-in-effect` et 21
      `no-misused-promises` d'abord *(§1.D)*
- [ ] Adoption du kit `ui/` (18 % des boutons) — par le lint, au fil de l'eau
      *(§2.A)*
- [ ] Unifier la persistance : SQLite + 7 JSON + 1 CSV → une seule vérité
      *(§1.B, §4.D)*
- [ ] Supprimer les 5 routes orphelines *(§1.C)*
- [ ] Renommer `objectif_type` → `garderobe_objectif_type` *(§5.D)*
- [ ] Sortir les constantes de score vers `/parametres` *(§4.F)*
- [ ] `role="tabpanel"` + `aria-controls` sur les onglets *(§2.G)*
- [ ] Brancher `<Freshness>` partout où la donnée vient d'un job ou d'une source
      externe *(§2.G)*
- [ ] Next 15 → 16, React 19.1 → 19.2, lucide 0.460 → 1.25, sonner 1 → 2,
      vitest 2 → 3, eslint 9 → 10 *(§1.G)*

---

## Hygiène disque (hors code)

Le dossier de projet porte **~3,3 Go d'artefacts jetables** :

```
.worktrees/            1 422 Mo   (53 860 fichiers — worktree « voyage-planificateur » abandonné)
backend/…xlsx          1 018 Mo   (67 251 fichiers de cache financier)
.claude/worktrees/       720 Mo   (2 worktrees d'agents abandonnés)
graphify-out/             81 Mo
backend/.codex-*          50 Mo
```

---

## Annexe — méthode

Toutes les mesures de ce document sont reproductibles :

```bash
# Dépôt
git count-objects -vH
git ls-files backend/data/financials_by_company | wc -l

# Base de données (depuis la racine)
.venv/Scripts/python.exe -c "import sqlite3; c=sqlite3.connect('data/mission-control.db'); \
  print(sorted(((c.execute(f'select count(*) from \"{t}\"').fetchone()[0], t) \
  for (t,) in c.execute(\"select name from sqlite_master where type='table'\")), reverse=True))"

# Lint
cd backend && uv run ruff check . --statistics
cd frontend && npx eslint . -f json -o eslint.json

# Types
cd frontend && npx tsc --noEmit          # propre au moment de l'audit

# Tests
cd backend && uv run pytest -q           # coupé à 55 % après 45 min, 1 échec

# Performance (backend lancé)
curl -s -o /dev/null -w "%{http_code} %{time_total}s %{size_download}b\n" \
  http://127.0.0.1:8000/api/v1/musique/tracks

# Adoption du design system
cd frontend && grep -rho "<button" components src --include=*.tsx | wc -l
cd frontend && grep -rho "<Button" components src --include=*.tsx | wc -l
```

**Non couvert par cet audit** : les tailles de bundle par route (le
`next build` a été interrompu deux fois par la limite de temps — les chunks
partagés font ~600 Ko non compressés et `.next/static` 2,6 Mo, mais ces chiffres
proviennent d'un build incomplet et ne doivent pas être cités tels quels).
La suite de tests backend n'a jamais terminé : il peut exister d'autres échecs
au-delà des 55 % atteints.
