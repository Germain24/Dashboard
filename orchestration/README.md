# Orchestration — organisation des documents

Tous les documents de travail (specs `-design.md` et plans d'implémentation) sont
regroupés ici et classés par avancement :

- **`finis/`** — plans et specs entièrement livrés (commités sur la branche).
  Un couple plan + spec y entre quand toutes ses tâches sont exécutées.
  Contient aussi `2026-07-04-improvements-p0-p1-navigation-design-perf.md`
  (§1/§2/§4 de la feuille de route P0-P3), `2026-07-16-improvements-p1-rangement-3.md`
  (§3 rangement, dernier morceau de P1), `AMELIORATIONS_200.txt` (items 1-255 et
  501-549, suivi item par item entièrement résolu ou explicitement abandonné) et
  l'audit Lighthouse.
- **`en-cours/`** — travaux commencés mais pas terminés. Vide actuellement (le
  dernier chantier, §3 rangement, est passé dans `finis/` le 2026-07-16).
- **`a-faire/`** — specs/plans rédigés mais dont l'exécution n'a pas commencé.
  Contient `ameliorations-p2-modules-qualite.md` (§5/§6 de la feuille de route,
  P2, partiellement exécuté le 2026-07-20 — voir la section de passe en tête du
  fichier) et `ameliorations-vague2-backlog.txt` (items 256-500 de
  `AMELIORATIONS_200.txt`, backlog d'idées, trié par pertinence le 2026-07-20).

> **Piège rencontré le 2026-07-20.** Sept plans dormaient dans `a-faire/` alors
> qu'ils étaient **entièrement livrés** (progression live du DE, seeds infinis +
> arrêt manuel, résilience DE, Super C unique phases 1-3) : leurs cases `- [ ]`
> n'avaient jamais été cochées et personne n'avait déplacé les fichiers. Les 47
> tests nommés dans ces plans existent et passent. Ils sont maintenant dans
> `finis/`.
>
> Avant de conclure qu'un plan de `a-faire/` reste à faire, **vérifier l'état
> réel du code** — les cases à cocher ne sont pas fiables ; les fichiers de test
> que le plan décrit, eux, le sont.

Cycle de vie : une nouvelle spec/plan naît dans `a-faire/`, passe dans
`en-cours/` dès la première tâche exécutée, puis dans `finis/` une fois tout
commité.

Restent à la racine d'`orchestration/` (documents vivants, référencés par le
code ou le README) :

- `PLAN.md` — document de référence du projet (architecture, règles).
- `CHANGELOG.md` — journal des livraisons.
- `logs/`, `graphify/` — historiques et graphe de connaissance.
