# CONV 3 — Récap de clôture

> À coller dans la conversation orchestrateur pour mettre à jour `PLAN.md`.

## Décisions prises au démarrage

| Question                              | Décision                                                                                          |
|---------------------------------------|---------------------------------------------------------------------------------------------------|
| Objectif explicite                    | Poids cible **71 kg** (depuis 51 kg) à ~10 % MG. Surplus +500 kcal jour sport / ×1.1 jour repos. |
| Composition corporelle tracée         | **Poids** quotidien + **photo_url** typée optionnelle. Tour de taille / % MG → champ JSON `extra` libre. |
| Lien Entraînement (intensité du jour) | **Placeholder V1** tranché par orchestrateur : champ optionnel `none/low/medium/high`, défaut date-based (lun/mar/mer/ven/sam = `medium`). CONV 7 surchargera. |
| Budget nutrition                      | Paramètre optionnel `budget_max_daily` dans `/plan/generate`, défaut 18 CAD/j (Prix_Max legacy). Pas d'intégration avec CONV 8. |
| Affichage micronutriments             | **Drawer latéral à la demande** : page jour = macros + prix, drawer = 25+ vitamines/minéraux.  |

## Stack effective

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.13 + scipy 1.14 + pandas 2.2
- **Frontend** : Next.js 15.5 + React 19.1 + TailwindCSS 4 (CSS variables shadcn-style)
- **Optimisation** : `scipy.optimize.minimize` SLSQP (port à l'identique du legacy)
- **Régression linéaire** : pure Python (sans scipy) pour rester testable sans la stack scientifique
- **Tests** : pytest 8.3, 71 tests verts incluant 36 nouveaux (sante)

## Livré (critères de succès du brief)

- [x] Historique poids importé et visible (CRUD `MesureSante` + page Composition)
- [x] Saisie poids du jour → re-calcule + génère plan (`POST /sante/plan/generate`)
- [x] Plan optimisé respecte macros + budget si défini (contraintes dures SLSQP)
- [x] Projection de poids cible avec date estimée (`GET /sante/projection`)
- [x] Tendance poids 7j et 30j affichées correctement (graphique SVG inline + cards)
- [x] Détail micronutriments accessible via drawer
- [x] Singleton `NutritionGoal` configurable depuis l'UI (onglet Objectif)
- [x] Intensité d'entraînement saisissable manuellement, défaut sport_days configurables
- [x] `pytest` passe (71 tests, dont 36 spécifiques santé)

## Schéma DB modifié

Migration `a1b2c3d4e5f6_sante_extend.py` (revises `cd9aba577b3c`) :

**`mesure_sante`** (existait) :
- `+ photo_url` (str, optionnel) — URL ou chemin local vers une photo de suivi
- `+ note` (str, optionnel) — note libre (ressenti, tour de taille, % MG en clair, etc.)

**`plan_nutrition`** (existait) :
- `+ poids_used` (float) — poids utilisé pour calculer les targets
- `+ intensite` (str) — `none / low / medium / high`
- `+ base_targets` (JSON) — targets avant compensation J-1
- `+ totals` (JSON) — totaux nutritifs effectifs
- `+ consumed` (JSON) — consommation réelle (alimente compensation J+1)
- `+ warning` (str) — message d'avertissement de l'optimiseur
- Index `date` passé de non-unique → unique

**`nutrition_goal`** (nouvelle, singleton logique `actif=True`) :
- `id`, `date_set`, `poids_cible`, `body_fat_target_pct`, `date_cible`
- `type` (bulk/cut/maintain)
- `surplus_kcal_sport` (float, défaut 500), `rest_factor` (float, défaut 1.1)
- `sport_days` (JSON list[int] ISO weekday, défaut `[0, 1, 2, 4, 5]` pour Germain)
- `actif` (bool indexé), `note`, `created_at`, `updated_at`

## Endpoints exposés (`/openapi.json`)

```
GET    /sante/ping                  -> { module: "sante", ready: true }

GET    /sante/mesures?days=180      -> liste historique
POST   /sante/mesures               -> upsert mesure (clé = date)
PATCH  /sante/mesures/{date}        -> édition partielle
DELETE /sante/mesures/{date}        -> suppression

GET    /sante/aliments              -> catalogue (68 lignes importées par CONV 1)

GET    /sante/goal                  -> objectif actif (auto-créé si absent)
PATCH  /sante/goal                  -> met à jour l'objectif (poids cible, sport_days, surplus…)

GET    /sante/targets/today         -> base + targets compensés (poids/intensity overrideable via query)

POST   /sante/plan/generate         -> optimise le plan, upsert PlanNutrition
GET    /sante/plan/today            -> plan du jour
GET    /sante/plan/{date}           -> plan d'une date donnée
PATCH  /sante/plan/{date}           -> édite quantités / consumed / warning

GET    /sante/projection?target_weight={x}  -> projection date d'atteinte
```

## Architecture livrée

```
backend/app/
├── models/sante.py                  (4 modèles : MesureSante, PlanNutrition, Aliment, NutritionGoal)
├── api/
│   ├── routes_sante.py              (15 endpoints)
│   └── schemas_sante.py             (Pydantic in/out, 12 schémas)
└── services/sante/
    ├── __init__.py                  (façade publique)
    ├── constants.py                 (RDA, mappings CSV ↔ keys, staples)
    ├── intensity.py                 (modificateurs none/low/medium/high + défaut date-based)
    ├── goal.py                      (singleton NutritionGoal helpers)
    ├── targets.py                   (calculate_daily_targets + compensation J-1)
    ├── aliments.py                  (chargement DB → DataFrame transposé)
    ├── optimizer.py                 (SLSQP scipy port du legacy)
    ├── totals.py                    (somme nutriments d'un plan)
    └── projection.py                (régression linéaire pure Python)

backend/tests/test_sante/            (36 tests)
├── test_intensity.py                (8 tests)
├── test_targets.py                  (8 tests, validation rétrocompat legacy)
├── test_projection.py               (6 tests)
├── test_optimizer.py                (3 tests sur catalogue synthétique)
└── test_api.py                      (11 tests d'intégration, DB SQLite isolée)

frontend/
├── src/app/sante/page.tsx           (mount du composant client)
├── lib/sante.ts                     (types + client API typé)
└── components/sante/
    ├── Sante.tsx                    (orchestrateur + tabs)
    ├── JourTab.tsx                  (plan + macros + tableau)
    ├── MacroBar.tsx                 (barre de progression réutilisable)
    ├── TendanceTab.tsx              (graphique SVG inline + stats)
    ├── CompositionTab.tsx           (formulaire mesure + tableau)
    ├── GoalTab.tsx                  (édition NutritionGoal)
    └── MicrosDrawer.tsx             (drawer ~27 micros)

backend/alembic/versions/
└── 20260516_1400_a1b2c3d4e5f6_sante_extend.py
```

## Surprises / décisions techniques utiles à retenir

1. **Re-mappage des nutriments CSV ↔ keys métier**. Le legacy mélange `Energie`/`Calories`,
   `Proteines`/`Protéines`, `Magnesium`/`Magnésium`, `Sodium`/`Sodium_Max`, etc. Centralisé
   dans `services/sante/constants.py` (`NUTRIENT_KEY_TO_CSV` + inverse). Tout passe par ce mapping.

2. **Sucres synthétiques**. Le CSV legacy stocke `Glucose`, `Fructose`, `Galactose`,
   `Saccharose`, `Lactose` séparément. L'optimiseur les somme en colonne dérivée `TotalSugars`
   (pré-calculée au chargement DataFrame). `Sucres_Max` côté métier mappe sur `TotalSugars` côté CSV.

3. **Pas de relecture du CSV à chaque optimisation**. Le legacy ré-ouvrait `aliments.csv`
   à chaque appel. Maintenant : `load_aliments_dataframe(session)` charge depuis la table
   `aliment` (importée par CONV 1) et retourne un DataFrame normalisé prêt pour l'optimiseur.

4. **Régression linéaire pure Python**. Pour la projection, j'ai évité scipy.stats.linregress
   exprès : ça permet de tester `projection.py` sans installer scipy. La logique est triviale
   (OLS), pas la peine d'une dépendance.

5. **Intensité = placeholder bien typé**. La fonction `intensity_modifiers(level, surplus_kcal_sport, rest_factor)`
   retourne explicitement `{activity_factor, surplus_kcal, protein_per_kg, lipid_per_kg}`.
   Le mapping pour `medium` reproduit exactement le legacy (×1.2, +500 kcal, 2.2 g/kg prot, 1.2 g/kg lip).
   Pour CONV 7 : l'endpoint `/api/entrainement/intensity/today` n'aura qu'à retourner un de
   ces 4 niveaux ; le code de calcul ne changera pas.

6. **Singleton NutritionGoal**. Plutôt qu'une table key-value ou un fichier de config,
   un vrai modèle SQL avec `actif=True` au plus une fois. Avantage : audit trail (anciens
   objectifs gardés en `actif=False`). `ensure_active_goal()` auto-crée un défaut compatible
   legacy si absent.

7. **Pydantic `model_validate(orm_instance)` vs `from_attributes`**. Tous les schemas Read
   ont `model_config = {"from_attributes": True}` (cf. CONV 2). Indispensable pour que
   `MesureSanteRead.model_validate(m)` accepte un objet SQLModel.

8. **Optimiseur peut renvoyer 422**. Si SLSQP ne converge pas dans la contrainte budget,
   `optimize_nutrition` retourne `(None, warning)`. La route propage en `422 Unprocessable
   Entity` avec le message d'erreur — différent du 500 (qu'on n'utilise jamais : c'est un
   "votre input est légitime mais le problème est insoluble", pas un crash serveur).

9. **Stable AVANT direction**. Le check `abs(slope) < 1e-4` (poids stable) doit venir
   AVANT le check "tendance va dans le mauvais sens" dans `project_weight_to_target`,
   sinon une pente de 0 + objectif > poids actuel tombe dans le mauvais sens. Bug détecté
   par un test, corrigé.

10. **Compensation J-1 sur tous les nutriments**. Pas seulement les calories — fibres,
    micronutriments, prix sont aussi compensés. Sauf `Poids_Corps` et `Prix_Max` (constantes
    de référence, pas des cibles à atteindre).

## Action utilisateur — finaliser CONV 3 chez Germain

### 1. Appliquer la migration

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
make migrate          # alembic upgrade head → applique a1b2c3d4e5f6
```

(Si tu repars d'une DB vide : `make migrate` joue les deux migrations dans l'ordre.)

### 2. Définir l'objectif initial

Une fois `make dev` lancé, va sur http://localhost:3000/sante → onglet **🎯 Objectif** et
saisis :

- Poids cible : 71 kg
- Masse grasse cible : 10 %
- Type : Bulk
- Surplus kcal jour sport : 500 (défaut)
- Facteur jour repos : 1.1 (défaut)
- Jours d'entraînement : Lun, Mar, Mer, Ven, Sam (déjà cochés)

### 3. Saisir le premier poids

Onglet **⚖️ Composition** → entre ton poids du jour (~51 kg). Tu peux aussi coller un
chemin/URL de photo si tu veux suivre l'évolution visuelle.

### 4. Générer le plan du jour

Onglet **🥗 Jour** → bouton **✨ Générer un plan**. Choisis l'intensité (par défaut le
lundi = `medium` = jour sport). L'optimiseur sort un plan respectant ton budget de 18 CAD
et tes macros.

### 5. (Optionnel) Saisir 30 jours d'historique pour la projection

La projection a besoin d'au moins 2 mesures de poids. Plus tu en saisis, plus la tendance
30j est fiable (`confidence` : low → medium ≥ 7 pts → high ≥ 20 pts).

## Prochaine CONV recommandée

**CONV 4 — Module Finance (suivi + Buffett mensuel)**. Brief dans
`orchestration/CONV4_finance.md`. Beaucoup plus dense — c'est le module avec le plus de
code legacy mature à porter (1920 lignes pour la partie Buffett).

Alternative : **CONV 7 — Entraînement** si tu veux que l'intensité d'entraînement soit
calculée automatiquement plutôt que saisie manuellement dans Santé.
