# Orchestration — organisation des documents

Tous les documents de travail (specs `-design.md` et plans d'implémentation) sont
regroupés ici et classés par avancement :

- **`finis/`** — plans et specs entièrement livrés (commités sur la branche).
  Un couple plan + spec y entre quand toutes ses tâches sont exécutées.
  Contient aussi `2026-07-04-improvements-p0-p1-navigation-design-perf.md`
  (§1/§2/§4 de la feuille de route P0-P3, terminés) et l'audit Lighthouse.
- **`en-cours/`** — travaux commencés mais pas terminés. Contient
  `improvements.md` : uniquement §3 (rangement, encore mixte fait/en attente)
  de la feuille de route P0-P3 depuis le découpage du 2026-07-04.
- **`a-faire/`** — specs/plans rédigés mais dont l'exécution n'a pas commencé.
  Contient `ameliorations-p2-modules-qualite.md` (§5/§6 de la feuille de route,
  P2, pas commencé) et `ameliorations-vague2-backlog.txt` (items 256-500 de
  `AMELIORATIONS_200.txt`, backlog d'idées très majoritairement non attaqué).

Cycle de vie : une nouvelle spec/plan naît dans `a-faire/`, passe dans
`en-cours/` dès la première tâche exécutée, puis dans `finis/` une fois tout
commité.

Restent à la racine (documents vivants, référencés par le code ou le README) :

- `PLAN.md` — document de référence du projet (architecture, règles).
- `CHANGELOG.md` — journal des livraisons.
- `AMELIORATIONS_200.txt` — suivi item par item (marquage FINIS daté), items
  1-255 et 501-549 (entièrement résolus). Le backlog non attaqué (256-500) vit
  dans `a-faire/ameliorations-vague2-backlog.txt` depuis le 2026-07-04.
- `logs/`, `graphify/` — historiques et graphe de connaissance.
