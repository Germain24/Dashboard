# CONV 15 — Tests, CI, documentation

## Objectif

Mettre un filet de sécurité sous le projet : tests automatisés sur la logique
métier critique (Python) + tests E2E sur les flows front (Next.js), CI GitHub,
README + docs.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée** et plusieurs autres modules
implémentés (sinon pas grand-chose à tester).

## État actuel

Aucun test, aucune CI, aucun README. La CONV 1 a juste créé un test
`/health` placeholder.

## Décisions à prendre

1. **Couverture cible** : 60 % global, 80 % sur la logique métier critique
   (nutrition optimizer, Buffett scoring, score thermique, GPA) ?
2. **Test runner Python** : pytest seul, ou + Hypothesis (property-based) ?
3. **Test runner front** : Vitest pour unitaires + Playwright pour E2E ?
4. **CI** : GitHub Actions ? OS ciblé Windows uniquement, ou aussi Linux ?
5. **Documentation** : README + `docs/` en Markdown plat, ou site MkDocs ?

## Livrable attendu

### Tests backend

```
backend/tests/
├── conftest.py                  # fixtures DB, client httpx
├── unit/
│   ├── test_sante_targets.py
│   ├── test_sante_optimizer.py
│   ├── test_finance_buffett_scoring.py
│   ├── test_garderobe_thermal.py
│   ├── test_garderobe_suggest.py
│   ├── test_agenda_recurrence.py
│   ├── test_agenda_slots.py
│   ├── test_etudes_gpa.py
│   ├── test_entrainement_1rm.py
│   ├── test_budget_rules.py
│   ├── test_cuisine_macros.py
│   └── test_habitudes_streaks.py
├── integration/
│   ├── test_api_garderobe.py
│   ├── test_api_finance.py
│   └── ... (un par module)
└── factories/                   # données de test
```

### Tests frontend

```
frontend/tests/
├── unit/                        # Vitest, composants
└── e2e/                         # Playwright
    ├── garderobe.spec.ts        # ajouter vêtement, valider tenue
    ├── sante.spec.ts            # logger poids, voir plan
    ├── finance.spec.ts          # voir portefeuille
    └── agent.spec.ts            # envoyer message, vérifier réponse
```

### CI

```
.github/workflows/
├── backend.yml                  # ruff + pytest + coverage
├── frontend.yml                 # eslint + vitest + playwright
└── e2e.yml                      # full stack docker-compose + playwright
```

### Documentation

```
docs/
├── architecture.md              # diagramme + explication
├── modules.md                   # description chaque module
├── api.md                       # link vers OpenAPI auto-gen
├── access.md                    # CONV 14
├── data-model.md                # schéma SQLite
├── developing.md                # comment contribuer
└── deployment.md                # comment relancer après crash, mises à jour
```

`README.md` à la racine : pitch projet, install, run, structure, liens vers
les docs détaillées.

## Tests prioritaires

1. **Santé — `calculate_daily_targets`** : vérifier formules (32 kcal/kg
   maintenance, +500 sport ×1.2, prot 2.2g/kg sport vs 1.6 repos).
2. **Santé — `optimize_nutrition`** : plan valide pour cibles standards.
3. **Garde-robe — `thermal_score`** : items connus.
4. **Garde-robe — `suggest_outfit`** : jamais d'item sale, contraintes météo.
5. **Finance — `get_portfolio`** : mock yfinance, vérifier normalisation poids.
6. **Finance — Buffett scoring** : sample tickers.
7. **Agenda — récurrence** : 5 cours répétés sur 4 semaines correctement.
8. **Agenda — slots** : trous correctement détectés.
9. **Études — GPA** : barème UQAM, pondération crédits.
10. **Habitudes — streaks** : reset après gap, record.

## Hors-scope

- Tests E2E exhaustifs (un flow critique par module suffit en V1)
- Couverture 100 % (faux signal)
- Tests de performance / charge (single-user)

## Dépendances

- Prérequis : CONV 1.
- Idéal : après Phases 2 et 3 (matière à tester).

## Suggestions techniques

- `pytest-mock` pour mocker yfinance et appels externes
- Fixtures Factory pour générer Vetements / Aliments / Transactions
- `ruff` config minimale : `select = ["E", "F", "I", "B", "UP", "SIM"]`
- Playwright config : 1 navigateur en CI (Chromium), tous en local
- OpenAPI → client TS : `openapi-typescript` dans la CI pour vérifier
  qu'aucun endpoint n'a divergé

## Critères de succès

- [ ] `pytest` tourne en < 30 s, coverage ≥ 60 %
- [ ] Tests E2E Playwright passent sur au moins 1 flow par module
- [ ] CI verte sur main
- [ ] README clair (install + run en < 5 min pour un nouveau cloneur)
- [ ] Diagramme d'architecture à jour dans `docs/architecture.md`

---

## Prompt d'amorce

```
Je veux mettre en place tests, CI et docs pour Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV15_tests_ci_doc.md

Pose-moi les 5 questions de "Décisions à prendre".
```
