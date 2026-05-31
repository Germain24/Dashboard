# CONV 2 — Récap de clôture

> À coller dans la conversation orchestrateur pour mettre à jour `PLAN.md`.

## Décisions prises au démarrage

| Question                                  | Décision                                                                 |
|-------------------------------------------|--------------------------------------------------------------------------|
| Pixel art PNG ou emojis ?                 | **PNG conservés** (23 fichiers), fallback emoji par catégorie si absent  |
| Auto-suggestion à l'ouverture ?           | **Auto 1×/jour** (clé `localStorage`), sinon bouton manuel               |
| Body en coton — règle thermique ?         | **Refondue** — body inclus dans l'espace de recherche de l'optimiseur    |
| API météo — OpenWeather ou autre ?        | **OpenWeather** (tier Free, clé `.env`) + fallback Open-Meteo automatique|

## Stack additions vs CONV 1

- **Provider météo abstrait** : `WeatherProvider` ABC + `OpenWeatherProvider` (préféré) + `OpenMeteoProvider` (fallback). Cache in-memory 30 min.
- **Variables `.env` ajoutées** : `OPENWEATHER_API_KEY`, `GARDEROBE_LAT`, `GARDEROBE_LON`, `GARDEROBE_HOUR_START`, `GARDEROBE_HOUR_END`, `GARDEROBE_WEATHER_CACHE_TTL`.
- **`httpx`** (déjà dans pyproject.toml CONV 1) utilisé pour les appels HTTP.

## Livré (critères de succès du brief)

- [x] Tous les vêtements importés visibles dans Inventaire (23 pièces depuis SQLite)
- [x] Suggestion automatique fonctionne avec la météo réelle (OpenWeather + fallback)
- [x] Validation d'une tenue persiste correctement (`portes +1`, history loggée en DB)
- [x] Stats identiques au Streamlit (à laver, par couleur, par catégorie, ratio 60/30/10)
- [x] Recommandations d'achat fonctionnelles (5 max, triées par potentiel)
- [x] Mobile-friendly (grille `grid-cols-3 sm:grid-cols-6`)
- [x] 33/35 tests pytest passent (les 2 échecs initiaux fixés en cours de session)

## Architecture livrée

```
backend/app/
├── api/
│   ├── routes_garderobe.py     # 11 endpoints REST
│   └── schemas_garderobe.py    # Pydantic 2 : 14 schémas
└── services/garderobe/
    ├── __init__.py
    ├── constants.py            # SLOTS (12), EMO_CAT, MATIERE_THERMIQUE, palette
    ├── state.py                # proprete_pct, vie_pct, needs_wash, is_worn_out
    ├── style.py                # style_score, colors_compat, get_color_category
    ├── thermal.py              # thermal_score, target_thermal, calculate_thermal_gap
    ├── optimizer.py            # suggest_outfit (body coton dans la recherche)
    ├── recommendations.py      # get_purchase_recommendations
    └── weather.py              # WeatherProvider + OpenWeather + Open-Meteo + cache

frontend/
├── lib/garderobe.ts            # Client API + types TS + helpers
├── components/garderobe/
│   ├── Garderobe.tsx           # Client component principal (5 onglets, state)
│   ├── WeatherBanner.tsx
│   ├── ThermalScore.tsx
│   ├── SlotCard.tsx
│   ├── InventaireTab.tsx
│   ├── StatsTab.tsx
│   ├── HistoriqueTab.tsx
│   └── RecommandationsTab.tsx
├── src/app/garderobe/page.tsx  # Page server, délègue à <Garderobe />
└── public/garderobe/assets/    # 23 PNG pixel art portés

backend/tests/test_garderobe/
├── test_state.py               # 7 tests
├── test_thermal.py             # 9 tests
├── test_style.py               # 7 tests
├── test_optimizer.py           # 7 tests
└── test_recommendations.py     # 4 tests
```

**Total : 3 034 LOC ajoutées (1 130 services back, 630 API, 375 tests, 899 front).**

## Endpoints exposés (`/garderobe/*`)

```
GET    /garderobe/vetements              liste + filtres (categorie, style, etat)
POST   /garderobe/vetements              création
GET    /garderobe/vetements/{id}         détail (avec champs dérivés)
PATCH  /garderobe/vetements/{id}         édition partielle
DELETE /garderobe/vetements/{id}
GET    /garderobe/meteo                  météo cachée 30 min (force_refresh=true bypasse)
GET    /garderobe/slots                  config des 12 slots (pour le front)
POST   /garderobe/suggest                suggestion de tenue (body coton dans la recherche)
POST   /garderobe/valider                portes +1, log dans tenue_history
GET    /garderobe/history                historique des tenues (limit configurable)
GET    /garderobe/stats                  distribution couleurs/cat/styles + à laver + HS
GET    /garderobe/recommendations        suggestions d'achat (top 5)
```

## Refonte de l'optimiseur (vs legacy)

Deux changements pour répondre à la décision « body coton refondu » :

1. **Cible thermique** = `50 − 1.5 × mean_window_temp`, où `mean_window_temp` est
   la moyenne du ressenti horaire entre 7h et 23h (paramétrable), au lieu de
   `(t_min + t_max) / 2` du legacy. Cohérent avec ce que le user porte vraiment
   pendant sa journée éveillée.
2. **Body coton dans l'espace de recherche** : pour chaque combinaison de slots
   valide (unicité + cohérence haut/bas), on évalue les deux variantes
   `use_body ∈ {False, True}` et on retient la combinaison qui **maximise le
   style_score parmi celles thermalement valides** (±4 de la cible). Plus de
   post-traitement « si gap > 1.5 alors active body ».

Reste à l'identique (port verbatim) : score thermique d'item, layering bonus
torse, filtre cohérence haut/bas, slots actifs météo, ajout greedy
d'accessoires optionnels après le solveur.

## Surprises / décisions techniques utiles à retenir

1. **Quand on instancie une garde-robe neuve** (tous items à `portes=0`), la
   logique legacy de « bloquer l'item le plus sale pour forcer la rotation »
   bloquait arbitrairement le premier item de la liste (tie sur score=0).
   Conséquence : le solveur ne pouvait jamais choisir un autre item dans la
   même catégorie. **Fix CONV 2** : on ne bloque que si l'item a déjà été
   porté (`score_rotation > 0`). À garder en tête si on rétroporte une autre
   règle de rotation.
2. **Sortie de `suggest_outfit` étendue** : on retourne maintenant
   `__use_body`, `__t_outfit`, `__target_thermal`, `__total_thermal`,
   `__style` en plus des 12 slots. Le front s'en sert pour afficher le score
   thermique sans rappel API.
3. **Auto-suggest 1×/jour côté client** : on stocke la date locale dans
   `localStorage["garderobe:lastSuggestionDate"]`. La validation de la tenue
   du jour efface cette clé pour réautoriser la suggestion du lendemain.
   Pas de table backend ajoutée — décision pragmatique pour V1.
4. **CORS** : la config CORS de CONV 1 autorise déjà `localhost:3000`, rien
   à ajouter.
5. **Test de ping CONV 1** : `tests/test_health.py::test_ping_modules`
   maintenait `"garderobe"` dans la liste des modules-stubs. Mis à jour pour
   l'enlever (garderobe a maintenant ses propres tests). Même opération
   à prévoir à la fin de chaque CONV Phase 2.

## Action utilisateur — commit Git

Le travail est sur disque mais pas dans l'histoire. Depuis PowerShell :

```powershell
cd C:\Users\germa\Documents\GitHub\mission-control

# Vérifier ce qui sera commité
git status

# Commit en plusieurs morceaux si tu veux découper proprement,
# sinon en un seul :
git add backend/app/services/garderobe/ backend/app/api/routes_garderobe.py `
        backend/app/api/schemas_garderobe.py backend/tests/test_garderobe/ `
        backend/tests/test_health.py backend/app/core/config.py `
        frontend/lib/garderobe.ts frontend/components/garderobe/ `
        frontend/src/app/garderobe/page.tsx frontend/public/garderobe/ `
        .env.example orchestration/CONV2_DONE.md

git commit -m "feat(garderobe): port module from Streamlit (CONV 2)

- 7 services métier (state, style, thermal, optimizer, recommendations,
  weather, constants) éclatant 641 lignes legacy
- 11 endpoints FastAPI sous /garderobe/* + 14 schémas Pydantic
- Provider OpenWeather (clé .env) + fallback Open-Meteo, cache 30 min
- Refonte body coton : inclus dans l'espace de recherche du solveur
- Cible thermique basée sur moyenne horaire 7h-23h (paramétrable)
- Frontend Next.js : 8 composants, 5 onglets, auto-suggest 1x/jour
- 23 PNG pixel art portés vers /public/garderobe/assets
- 34 tests pytest (state, thermal, style, optimizer, recommendations)"
```

**Note** : ton `git status` montre aussi des modifications dans `legacy_code/`
et plusieurs fichiers `data/imports/` — ces modifs ne viennent **pas** de
CONV 2 (rien n'a été écrit dans `legacy_code/` côté backend). Vérifie avant
de commiter pour ne pas les inclure par erreur. Probable changement de
line-endings (CRLF/LF) ou édition manuelle antérieure.

**Note 2** : régénère la clé OpenWeather sur openweathermap.org si elle a
transité par un chat (par sécurité, hygiène).

## Tests

```
33/35 passed au premier run, 35/35 après les 2 fixes appliqués en fin de
session (return manquant dans optimizer.py + retrait de garderobe du test
de stub-ping CONV 1).
```

## Prochaine CONV recommandée

**CONV 3 — Module Santé / Nutrition**. Données legacy déjà en DB
(`mesure_sante` 9 lignes, `plan_nutrition` 10, `aliment` 68) — on voit
immédiatement quelque chose à l'écran. Les patterns CONV 2 (services
éclatés, schémas, frontend par onglets) se généralisent bien.

Le brief `orchestration/CONV3_sante_nutrition.md` existe déjà.
