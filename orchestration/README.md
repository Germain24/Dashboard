# Orchestration — organisation des documents

Tous les documents de travail (specs `-design.md` et plans d'implémentation) sont
regroupés ici et classés par avancement :

- **`finis/`** — plans et specs entièrement livrés (commités sur la branche).
  Un couple plan + spec y entre quand toutes ses tâches sont exécutées.
- **`en-cours/`** — travaux commencés mais pas terminés. Contient notamment
  `improvements.md`, la feuille de route P0-P3 (P0 livré le 2026-07-02 ;
  P1 = adoption des primitives `ui/` + Verre Clair).
- **`a-faire/`** — specs/plans rédigés mais dont l'exécution n'a pas commencé.

Cycle de vie : une nouvelle spec/plan naît dans `a-faire/`, passe dans
`en-cours/` dès la première tâche exécutée, puis dans `finis/` une fois tout
commité.

Restent à la racine (documents vivants, référencés par le code ou le README) :

- `PLAN.md` — document de référence du projet (architecture, règles).
- `CHANGELOG.md` — journal des livraisons.
- `AMELIORATIONS_200.txt` — suivi item par item (marquage FINIS daté).
- `logs/`, `graphify/` — historiques et graphe de connaissance.
