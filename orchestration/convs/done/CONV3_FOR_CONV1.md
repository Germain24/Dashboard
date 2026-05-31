# CONV 3 — Message pour l'orchestrateur (CONV 1)

> À coller dans la conversation orchestrateur pour mettre à jour `PLAN.md`.
> Complète `CONV3_DONE.md` qui a tous les détails techniques.

## TL;DR

**CONV 3 (Module Santé / Nutrition) est terminée.** Vertical slice complet :
backend FastAPI + frontend Next.js + 36 tests verts. Commit unique
`ac38f21 feat(sante): port module from Streamlit (CONV 3)` sur `main`.

## Statut à mettre à jour dans PLAN.md

Dans le tableau "Phase 2 — Port des modules existants" :

```diff
- | CONV 3| Module Santé / Nutrition                       | À faire |
+ | CONV 3| Module Santé / Nutrition                       | **✅ Terminée 2026-05-17** (commit ac38f21) |
```

Dans le tableau "État actuel" :

```diff
- | Santé       | 505 lignes                  | mesure_sante (9), plan_nutrition (10), aliment (68)   | CONV 3    |
+ | Santé       | ✅ porté                    | mesure_sante (+photo/note), plan_nutrition (+5 cols), aliment, nutrition_goal (nouveau) | **Fait** |
```

## Décisions prises pendant CONV 3 (pour ta mémoire)

| Question                | Décision Germain                                              |
|-------------------------|---------------------------------------------------------------|
| Objectif                | 51 → 71 kg, ~10 % MG, type bulk. Sport lun/mar/mer/ven/sam.   |
| Composition trackée     | Poids + photo_url. Tour de taille / %MG → champ JSON `extra`. |
| Budget nutrition        | Param optionnel /plan/generate, défaut 18 CAD/j (legacy).     |
| Affichage micros        | Drawer à la demande (~27 micronutriments).                    |
| Intensité (toi)         | Placeholder V1 tranché, default Mon-Tue-Wed-Fri-Sat = medium. |

## Ce qui a été livré

**Schéma DB** (migration `a1b2c3d4e5f6_sante_extend.py`) :
- `mesure_sante` : +`photo_url`, +`note`
- `plan_nutrition` : +`poids_used`, +`intensite`, +`base_targets`, +`totals`, +`consumed`, +`warning` ; unicité date
- `nutrition_goal` : **nouvelle table** (singleton actif, surplus/rest_factor/sport_days configurables)

**Endpoints `/sante/*`** (15 au total) :
```
mesures (GET/POST/PATCH/DELETE), aliments (GET), goal (GET/PATCH),
targets/today (GET), plan/generate (POST), plan/today (GET),
plan/{date} (GET/PATCH), projection (GET)
```

**Frontend** : 4 onglets (Jour / Tendance / Composition / Objectif) + drawer micros, graphique SVG inline pour la tendance 90j, projection date d'atteinte.

**Tests** : 36 nouveaux dans `tests/test_sante/` ; 71 au total verts (avec garderobe et health).

## Points à garder en tête pour CONV 7 (Entraînement)

CONV 7 devra exposer un endpoint qui retourne `intensity: none | low | medium | high`
pour une date donnée, basé sur la séance planifiée. Le code Santé l'appellera à la
place du `default_intensity_for_date()` actuel. **Aucune modification de
`services/sante/intensity.py` ne sera nécessaire** — il suffira de remplacer
l'appel au défaut date-based par un appel HTTP/import direct vers le module
entraînement dans `routes_sante.py`.

Le mapping intensité → modificateurs (`activity_factor`, `surplus_kcal`,
`protein_per_kg`, `lipid_per_kg`) est figé dans `intensity_modifiers()` et n'a
pas besoin de changer.

## Surprises notables (à anticiper pour les prochaines CONV)

1. **Sandbox Linux + Git Windows** : le sandbox ne peut pas écrire dans `.git/index`.
   Contournement utilisé : `GIT_INDEX_FILE=/tmp/git_index_xxx git add/commit`. À
   prévoir pour CONV 4+ : les futures CONV peuvent avoir besoin du même hack.
2. **Tool Write tronque les gros fichiers Python (>200 lignes)**. Contournement :
   passer par `cat > file << 'EOF' ... EOF` en bash pour les fichiers critiques.
   Recommandation pour les prochaines CONV : structurer le code en sous-modules
   de <200 lignes chacun.
3. **Imports de pandas/scipy lourds** : les services Santé chargent `pandas` et
   `scipy.optimize` dès l'import du package. Pour les tests purs (intensity,
   targets, projection), j'ai gardé une logique sans pandas/scipy → ces tests
   tournent en <1 s même sans la stack scientifique installée.

## Prochaine CONV recommandée

Brief existant : **CONV 4 — Module Finance** (le plus volumineux : 1920 lignes
de logique Buffett legacy). Si tu veux que CONV 7 (Entraînement) câble la vraie
intensité d'entraînement avant que Germain n'utilise Santé en production,
CONV 7 est aussi un bon candidat — le placeholder actuel fonctionne mais sera
remplacé.

Mon vote : **CONV 4 d'abord** (Finance est plus dense et plus indépendant ;
CONV 7 pourra venir ensuite sans toucher au code Santé déjà livré).
