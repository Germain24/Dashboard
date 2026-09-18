---
target: Tout (frontend/components)
total_score: 28
p0_count: 0
p1_count: 0
timestamp: 2026-06-05T15-34-16Z
slug: frontend-components
---
# Re-critique — Frontend Mission Control (frontend/components, « Tout »)

## Design Health Score — 28/40 (Good, ↑ de 26)

| # | Heuristique | Avant | Maintenant | Note |
|---|-----------|:--:|:--:|------|
| 1 | Visibility of System Status | 3 | 3 | RevisionTab gagne skeleton/erreur ; reste des tabs Études sans états |
| 2 | Match System / Real World | 3 | 3 | inchangé |
| 3 | User Control & Freedom | 2 | 2 | RevisionTab a un confirm ; Cours/Deadlines/Sessions suppriment sans garde-fou |
| 4 | Consistency & Standards | 2 | 3 | tout Études passé aux tokens ; reste les boutons bruts vs primitives |
| 5 | Error Prevention | 2 | 2 | confirm seulement sur RevisionTab |
| 6 | Recognition > Recall | 3 | 3 | inchangé |
| 7 | Flexibility & Efficiency | 3 | 3 | inchangé |
| 8 | Aesthetic & Minimalist | 3 | 4 | tell violet + texte invisible éliminés : cohésion nette |
| 9 | Error Recovery | 2 | 2 | RevisionTab toaste ; StatistiquesTab avale encore |
| 10 | Help & Documentation | 3 | 3 | inchangé |

## Anti-Patterns Verdict
Scan déterministe : 0 finding sur tout frontend/components (était 1 — text-violet-400).
LLM : le tell « AI/SaaS violet » a disparu ; texte invisible (--muted surface) et cartes transparentes (--card-bg) corrigés sur les 6 onglets Études. Cohérence Heritage tenue de bout en bout. Pas de superposition navigateur.

## What's Working
1. Cohérence couleur app-wide : plus une couleur hors-token dans Études ; heatmap/barres thème-aware via --ring/color-mix.
2. Lisibilité réparée : --muted (invisible) -> --muted-foreground partout.
3. RevisionTab = référence propre (primitives + tokens + états + confirm).

## Priority Issues (backlog P2/P3)
- [P2] Trou d'états loading/erreur : StatistiquesTab avale les erreurs ; CoursTab/SessionsTab/DeadlinesTab/GpaTab sans skeleton ni erreur. -> harden.
- [P2] Suppressions sans garde-fou hors RevisionTab (Cours, Deadlines, Sessions). -> harden.
- [P2] Vocabulaire de composants : boutons/inputs bruts vs primitives ui/. -> refactor/polish.
- [P3] Emojis comme iconographie vs lucide.
- [P3] a11y formulaires : 10x label sans htmlFor.

## Persona Red Flags
Sam (a11y) : net progrès (contraste réparé, couleurs thème-aware) ; restent labels non associés + petites cibles ✕.
Alex : toujours bien servi.
