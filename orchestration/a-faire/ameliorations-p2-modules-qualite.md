# Mission Control — Améliorations P2 : enrichir les modules, qualité & DX (à faire)

> Extrait de `orchestration/en-cours/improvements.md` le 2026-07-04 : §5
> (enrichir les modules « automatisation de vie ») et §6 (qualité & DX) n'ont
> pas encore commencé — seule une puce de §5.4 (garde-robe) est déjà livrée
> (notée ci-dessous). Déplacés ici (P2, pas encore attaqué) pour ne pas les
> mélanger avec §1/§2/§4 (livrés, dans `orchestration/finis/`) et §3 (encore
> mixte, resté dans `orchestration/en-cours/improvements.md`).
>
> Contraintes non négociables (héritées du contexte d'origine) : pas d'IA
> conversationnelle ni d'aides vocales dans le dashboard ; l'arborescence est
> synchronisée avec graphify (l'utilisateur gère la sync) ; les données réelles
> (Desjardins, nutrition, Buffett, garde-robe) restent la source de vérité —
> les mock data ne servent qu'aux intégrations pas encore branchées.

Légende : [S] petit · [M] moyen · [L] gros — (\*) confort · (\*\*) valeur réelle · (\*\*\*) structurant

---

## Passe d'exécution du 2026-07-20

Plusieurs puces étaient en fait **déjà couvertes** — vérifié dans le code avant
d'écrire quoi que ce soit :

- §5.1 « métriques quantitatives » : `services/finance/risk.py` calculait déjà
  max drawdown, volatilité annualisée, HHI, Sharpe et l'exposition sectorielle
  (`compute_sector_diversification`), exposés par `GET /finance/risk`. Seul le
  **Sortino** manquait.
- §5.2 « le tracker macros dérive ses cibles de l'optimiseur » : l'UI le fait
  déjà (`PlanSemaineTab.tsx` lit `/sante/targets/today` puis passe les cibles au
  plan). La dette « cibles codées en dur » ne vivait plus que dans le **défaut**
  de `GeneratePlanRequest.cibles` (2500 kcal / 180 g pour un utilisateur de
  ~57 kg) — corrigé : cibles omises = dérivées de `calculate_daily_targets`,
  et 400 explicite si aucun poids n'est connu, plutôt qu'un profil inventé.
- §5.3 « statuts / progression / notes de lecture » : `Book` a déjà `statut`,
  `page_courante`, `date_debut`/`date_fin`, plus `BookNote`, `BookQuote` et
  `ReadingSession`. Seul le support **séries/tomes** manquait.

**Deux bugs trouvés au passage** (hors périmètre initial, corrigés) :

1. La ligne « 🍽️ Objectif : X kcal / Yg protéines » du briefing du matin n'est
   jamais sortie depuis son introduction. `calculate_daily_targets` renvoie un
   tuple `(base, compensé)` à clés capitalisées et accentuées, le briefing
   appelait `.get("calories")` dessus → `AttributeError` avalée par un
   `except Exception: pass`.
2. `/finance/risk` perdait **volatilité et concentration** depuis toujours :
   `get_risk_metrics` produit `volatilite_annualisee_pct` / `concentration`, le
   schéma `RiskMetricsOut` déclarait `volatilite_annuelle_pct` / `hhi_label`.
   Pydantic ignore les clés en trop et remplit les manquantes par défaut →
   l'endpoint répondait `0.0` et `"—"` quelles que soient les données, sans
   jamais lever d'erreur. Troisième orthographe au passage : la branche « pas de
   données » renvoyait `volatilite_pct`. Schéma réaligné sur les clés du service
   (celles que les tests existants asservissent), branche vide corrigée, et les
   deux champs enfin affichés dans `RiskMetricsRow`.

Tests de non-régression ajoutés dans les deux cas.

**Écarté volontairement**, avec la raison :

- §5.1 adaptateur **OpenBB** — introduit une dépendance lourde pour remplacer
  yfinance, qui fonctionne et dont les pannes réelles (rate-limit) ont déjà été
  traitées. L'abstraction `MarketDataProvider` ne se justifie qu'avec un second
  fournisseur réellement voulu ; aucun besoin exprimé.
- §5.2 ingestion **Strava/GPX/TCX** — aucun export à ingérer : construire le
  parseur et sa table sur des fixtures inventées reviendrait à écrire un module
  contre des données qui n'existent pas. À rouvrir le jour où il y a un fichier
  réel à importer.
- §5.3 **seed d'exemple** si la base est vide — contredit la règle « les données
  réelles sont la source de vérité » ; du faux contenu dans une bibliothèque
  personnelle se confond vite avec de vraies entrées.
- §5.2 corrélations : la formulation d'origine (« score / sommeil / nutrition »)
  est circulaire — le score EST calculé à partir de sommeil + sport + nutrition.
  Livré avec les seules cibles qui aient un sens : humeur, énergie, poids, qui
  n'entrent pas dans la formule (`GET /sante/score/correlations`).

---

## 5. Modules « automatisation de vie » — enrichir l'existant (P2)

> Tous les modules demandés existent déjà avec de vraies données. Les mock data ne
> sont introduites **que** pour les intégrations non branchées, sous forme de
> fixtures de test + adaptateurs prêts à recevoir le vrai flux.

### 5.1 Dashboard quantitatif & Finance
- [M](\*\*\*) Métriques quantitatives calculées sur le ledger réel : Sharpe, Sortino,
  volatilité annualisée, max drawdown, exposition par secteur (le TWR et le HHI
  existent déjà dans `services/finance/`).   ← FINIS ✓ (2026-07-20) Tout existait
  sauf **Sortino** : ajouté (`compute_sortino`, conventions de `compute_sharpe` —
  MAR quotidien géométrique, Bessel n-1 sur l'échantillon complet, somme
  restreinte aux rendements baissiers). `None` quand aucun rendement n'est sous
  le MAR : le ratio est infini, `0.0` se lirait « mauvais ».
  **Aucun composant ne consommait `/finance/risk`** (`useRisk()` n'avait aucun
  site d'appel) → `RiskMetricsRow` créé et monté dans SuiviTab.
- [M](\*\*) Adaptateur d'ingestion **OpenBB** : interface `MarketDataProvider` avec
  implémentation yfinance actuelle + implémentation OpenBB derrière un flag ;
  fixtures mock pour les tests uniquement.
- [S](\*) Volumes quotidiens et mini-sparklines sur les positions du portefeuille.

### 5.2 Performance & Physiologie
- [S](\*\*) Le tracker macros dérive déjà ses cibles de l'optimiseur nutrition
  (profil réel ~57 kg) — vérifier que la liste d'épicerie consomme bien
  `calculate_daily_targets` (dette connue : cibles encore codées en dur).
  ← FINIS ✓ (2026-07-20) L'UI consommait déjà la bonne source ; le profil codé
  en dur ne subsistait que dans le défaut de `GeneratePlanRequest.cibles`.
  Supprimé : cibles omises = dérivées du dernier poids connu, 400 explicite si
  aucun poids. 3 tests TDD (`test_plan_cibles_source.py`).
- [M](\*\*) Ingestion d'exports **Strava/GPX/TCX** : parseur + table `SeanceImportee`,
  fixtures d'exemple calibrées (57 kg) pour les tests ; l'UI entraînement existante
  affiche les séances importées à côté du mésocycle.
- [S](\*) Corrélations simples score/sommeil/nutrition sur la page `/score` existante.
  ← FINIS ✓ (2026-07-20) Reformulé : sommeil/sport/nutrition sont les **entrées**
  du score, les corréler à lui ne mesurerait que sa formule. Livré contre les
  signaux hors formule — humeur, énergie, poids — via
  `services/sante/score_correlations.py` (réutilise `correlate_series` du
  journal, déjà testé) + `GET /sante/score/correlations` + section sur `/score`.
  3 tests TDD.

### 5.3 Knowledge & Library
- [M](\*\*) Enrichir `livres/` : statuts (en cours/terminé/pile à lire), progression,
  notes de lecture ; support séries/mangas (tomes) à côté des essais.
  ← FINIS ✓ (2026-07-20) Statuts/progression/notes existaient déjà (`Book.statut`,
  `page_courante`, `BookNote`, `BookQuote`, `ReadingSession`). Ajout du seul
  manque, **séries/tomes** : colonnes `serie`/`tome` + migration
  `l530_book_serie_tome`, `group_series_pure` (tomes `None` triés en dernier —
  un hors-série ou une numérotation trouée ne doit pas planter la comparaison),
  `GET /livres/series`, `SeriesShelf` dans BibliothequeTab (groupement
  client-side pour que les filtres statut/langue/tri continuent de s'appliquer)
  et saisie série/tome dans `BookDetailModal` — sans quoi aucun livre n'aurait
  jamais pu être rattaché à une série depuis l'UI. Attention : le vocabulaire de
  statut est `lu`, pas `termine`.
- [S](\*) Si la base est vide au premier lancement : seed d'exemple optionnel
  (Housel, Lynch, une série manga) clairement marqué « exemple », jamais mélangé
  aux vraies entrées.

### 5.4 Logistique & Planification
- [S](\*\*) Voyage : la carte Leaflet vient d'être livrée — checklist par voyage et
  budget par étape comme prochains incréments. ← FINIS ✓ (2026-07-20)
  `POST /voyage/confirmer` persiste désormais l'itinéraire retenu (`voyage`,
  `voyage_etape`, `voyage_checklist_item`) ; le coût estimé par étape réutilise
  `services/voyage/costs.py`, le coût réel se saisit étape par étape.
- [M](\*\*) Garde-robe : conseils d'achat combinatoires + enrichissement BonneGueule
  livrés (plans dans `orchestration/finis/`). ← FINIS ✓ (2026-07-01)
  Module garde-robe complet, plus rien en attente.
- [S](\*) Objectifs long-terme : jalons datés + lien vers les modules concernés
  (un objectif « épargne X $ » pointe vers patrimoine). ← FINIS ✓ (2026-07-20)
  Le lien vers les modules existait déjà via `LifeGoal.objectifs[].metric` ;
  seule la date manquait. Champ `date` optionnel sur le sous-objectif + statut
  dérivé (à venir / en retard / atteint), rétrocompatible avec le JSON stocké
  sans date. `ObjectifsVie` est désormais aussi affiché sur `/objectifs`.

  ⚠️ **Décision en attente, volontairement pas tranchée ici** : deux modèles
  d'objectifs coexistent. `LongTermGoal` (`/objectifs/goals`) est une barre 0-100
  déplacée à la main, sans lien vers les autres modules ; `LifeGoal` porte les
  sous-objectifs rattachés à une métrique réelle (poids, épargne, habitudes) et
  n'était rendu que sur `/vue-360`. Les jalons datés sont allés sur `LifeGoal`,
  le seul qui sache mesurer quoi que ce soit — et `/objectifs` affiche
  maintenant **les deux**, ce qui est honnête mais expose deux systèmes
  d'objectifs sur la même page. Les unifier (probablement : absorber
  `LongTermGoal` dans `LifeGoal` avec une métrique « manuelle ») demande un
  choix produit + une migration de données, hors périmètre de cette passe.

## 6. Qualité & DX (P2)

6.1 [S](\*\*) CI : passer le lint d'advisory à bloquant, règle par règle (la dette est
    déjà suivie séparément).   ← FINIS ✓ (2026-07-20) Ratchet : `backend/ruff-ci.toml`
    sélectionne les ~78 codes déjà à zéro violation (F821, B006, E722, UP006…),
    joué en étape CI **bloquante** ; l'étape advisory sur E/F/I/B/UP en entier
    (1770 violations) reste à côté. B008 exclu définitivement (`Depends()` en
    argument par défaut = patron FastAPI normal, 374 occurrences légitimes).
    Aucune ligne de code réécrite. Vérifié : `uv run ruff check . --config
    ruff-ci.toml` → « All checks passed! ».
6.2 [S](\*\*) Étendre les snapshots visuels Playwright aux états animés stabilisés
    (attendre la fin des transitions avant capture).   ← ÉCRIT, NON VÉRIFIÉ
    (2026-07-20) `frontend/e2e/visual-animated.spec.ts` : capture avec
    `animations: 'disabled'` (Playwright avance les transitions à leur état final
    puis les fige) après attente **sur la donnée** — les `.bar-fill` n'ont leur
    largeur inline qu'à l'arrivée de la réponse TanStack, donc un `waitForTimeout`
    seul ne garantit rien. Non exécuté ici : demande le stack complet lancé et la
    génération des références (`npm run test:e2e:update`). Volontairement **pas**
    ajouté au chemin CI bloquant tant qu'il n'a pas tourné au moins une fois.
6.3 [S](\*) `gen:types` vérifié en CI (diff vide entre OpenAPI et `lib/types.ts`).
    ← FINIS ✓ (2026-07-20, advisory) Job CI `types` (seul à avoir besoin de Python
    ET Node) : `scripts/dump_openapi.py` (dump sans serveur, `npm run gen:types`
    exige un uvicorn lancé) → `gen:types:file` → `git diff --exit-code`.
    **Laissé advisory** : `lib/types.ts` a déjà dérivé dans les deux sens (routes
    supprimées encore présentes, `/finance/portfolio/progress` manquante) et le
    resynchroniser au milieu d'un arbre de travail chargé aurait noyé le diff.
    Passer bloquant = rejouer `gen:types`, commiter, retirer `continue-on-error`.
6.4 [S](\*) Un `docs/CONTRIBUTING.md` court : conventions commits, TDD, workflow
    AMELIORATIONS, sync graphify.   ← FINIS ✓ (2026-07-20) Couvre en plus les
    contraintes produit (pas d'IA, pas de vocal, local-first, données réelles) et
    le piège « plan livré resté dans a-faire/ » rencontré dans cette passe.
