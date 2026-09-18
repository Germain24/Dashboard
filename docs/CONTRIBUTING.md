# Contribuer à Mission Control

Dashboard personnel mono-utilisateur, local-first. Backend FastAPI + SQLModel/SQLite,
frontend Next.js/React.

## Commits

Conventional Commits, description en français **sans accents** (contrainte du terminal
Windows utilisé pour le dépôt) :

```
feat(buffett): colonne Volume en euros a l'ingestion (scoring + ETF)
fix(courses): scraper circulaire Super C via API digital-flyer (etait 0 item)
docs(orchestration): spec+plan volume EUR livres
```

Portées courantes : `buffett`, `finance`, `courses`, `nutrition`, `impots`, `risk`,
`transactions`, `orchestration`. Un commit = un changement cohérent ; `wip:` est toléré
pour du travail en vol, pas comme état final.

## TDD

Le test échouant s'écrit **avant** l'implémentation, y compris pour un correctif : il doit
reproduire le bug et échouer pour la bonne raison avant d'être corrigé.

Les tests qui touchent aux données financières réelles doivent isoler **tous** les chemins
(`Config.CACHE_FILE`, `ToutBroker.xlsx`, `params.json`) vers `tmp_path`. Le serveur de dev
tourne souvent en parallèle avec le même CWD : un test non isolé écrit dans les vraies
données de l'utilisateur.

## Lancer les tests

```bash
make test                         # backend + frontend

cd backend && uv run pytest       # tout le backend
cd backend && uv run pytest -v tests/test_finance/test_risk.py

cd frontend && npx vitest run     # tout le frontend
cd frontend && npx vitest run __tests__/components/de-starr-chart.test.tsx
```

La CI ne joue qu'un **sous-ensemble hors-ligne** (`tests/test_budget/`, `test_habitudes/`,
`test_livres/`, `test_cuisine/`, `test_scheduler/`, plus health/cors/rate-limit) : tout ce
qui appelle yfinance, les taux de change, les cours ou Google Calendar a besoin du réseau
et ne tourne qu'en local.

## Lint

`backend/ruff-ci.toml` définit le jeu de règles **bloquant** en CI — celles qui sont déjà à
zéro violation. Le reste de la dette ruff (~1770 violations sur E/F/I/B/UP) reste advisory.

Pour faire avancer le ratchet : corriger une règle de la dette (`cd backend && uv run ruff
check . --statistics`), puis ajouter son code à `ruff-ci.toml`. Ne jamais élargir le
sélecteur bloquant sans avoir corrigé la règle d'abord — la CI doit rester verte.

## Specs et plans (`orchestration/`)

Les documents de travail sont classés **par avancement**, pas par thème :

| Dossier | Contenu |
|---|---|
| `a-faire/` | spec/plan rédigé, exécution pas commencée |
| `en-cours/` | au moins une tâche exécutée, pas fini |
| `finis/` | entièrement livré et commité |

Une nouvelle spec naît dans `a-faire/` et se déplace au fil de l'avancement. Un plan livré
qui reste dans `a-faire/` est un piège : on le relit plus tard en croyant qu'il reste à
faire. Vérifier l'état réel du code (les tests du plan existent-ils et passent-ils ?) avant
de conclure qu'un plan est à faire.

`orchestration/PLAN.md` (architecture, règles) et `orchestration/CHANGELOG.md` (journal des
livraisons) restent à la racine — ce sont des documents vivants.

Le backlog d'idées vit dans `orchestration/finis/AMELIORATIONS_200.txt` (items résolus) et
`orchestration/a-faire/ameliorations-vague2-backlog.txt` (items 256-500). Chaque item
terminé est daté : `← FINIS ✓ (AAAA-MM-JJ) <note>`, chaque item écarté :
`← ABANDONNÉ ✗ (AAAA-MM-JJ) <raison>`.

## Périmètre du produit

Contraintes non négociables, à connaître avant de proposer une fonctionnalité :

- **Pas d'IA conversationnelle** ni de génération de texte dans le dashboard.
- **Pas de commande vocale** (STT/TTS) ni d'aides handicap — outil mono-utilisateur ;
  l'ergonomie générale reste traitée normalement.
- **Local-first** : pas de dépendance à un service en ligne pour le cœur du produit.
- **Les données réelles sont la source de vérité** (Desjardins, nutrition, Buffett,
  garde-robe). Les mock data ne servent qu'aux tests et aux intégrations pas encore
  branchées — jamais mélangées aux vraies entrées.

## graphify

Le dépôt a un graphe de connaissance dans `orchestration/graphify/`. Pour une question sur
le code, `graphify query "<question>"` renvoie un sous-graphe ciblé, bien plus petit que
`GRAPH_REPORT.md` ou un grep brut.

**La synchronisation du graphe est gérée par l'utilisateur** : ne pas lancer
`graphify update` soi-même.
