---
target: Tout (frontend/components)
total_score: 26
p0_count: 0
p1_count: 3
timestamp: 2026-06-05T05-54-13Z
slug: frontend-components
---
# Critique — Frontend Mission Control (frontend/components, « Tout »)

## Design Health Score — 26/40 (Acceptable)

| # | Heuristique | Score | Problème clé |
|---|-----------|-------|----------|
| 1 | Visibility of System Status | 3 | Skeletons/toasts/Freshness excellents au cœur ; RevisionTab charge sans skeleton ni erreur |
| 2 | Match System / Real World | 3 | fr-CA naturel ; jargon MEV/MRV, RPE atténué par libellés |
| 3 | User Control & Freedom | 2 | Suppressions (fiche ✕, série, séance) immédiates, sans annuler/confirmer |
| 4 | Consistency & Standards | 2 | Tokens solides, mais violet/ambre/hex en dur + boutons bruts hors ui/ |
| 5 | Error Prevention | 2 | Aucune confirmation avant action destructive |
| 6 | Recognition > Recall | 3 | ⌘K, datalists, labels sur icônes |
| 7 | Flexibility & Efficiency | 3 | Palette commandes, j/k, densité, Pomodoro |
| 8 | Aesthetic & Minimalist | 3 | Système éditorial épuré ; emojis ad hoc cassent l'iconographie lucide |
| 9 | Error Recovery | 2 | TodayPanel = retry/toast exemplaire ; RevisionTab avale les erreurs |
| 10 | Help & Documentation | 3 | Aide raccourcis (?), états vides pédagogiques |

## Anti-Patterns Verdict
Globalement PAS « AI-made » : système Heritage à vraie voix. Mais un tell perce : le VIOLET, étranger à la marque (marine/bordeaux/vert).
Scan déterministe : 1 finding — ai-color-palette, text-violet-400 sur titre, etudes/StatistiquesTab.tsx:66.
Manqué par le détecteur : violet répété dans RevisionTab.tsx (bg-violet-600/700), couleurs de notation en hex bruts (#ef4444/#f59e0b/#10b981/#3b82f6), MuscleVolumePanel text-amber-600. Valeurs non-tokenisées → ignorent le thème sombre + la règle One Voice.
Pas de superposition navigateur (aucun serveur de dev ; injection non tentée).

## What's Working
1. Gestion d'état exemplaire au cœur : TodayPanel (skeleton → erreur+réessai → vide) + complétion optimiste rollback/toast.
2. Accessibilité pensée : nav active à 3 indices redondants, focus-visible global, prefers-reduced-motion.
3. Identité tenue : tokens, cva, serif réservé aux titres.

## Priority Issues
- [P1] Texte quasi invisible : text-[var(--muted)] utilisé comme couleur de texte (RevisionTab, ~5 occurrences). --muted (#efeeea) est une surface, pas du texte → illisible sur carte blanche. Viole Ink-on-Paper + contraste 4.5:1. Fix : --muted-foreground. → /impeccable polish.
- [P1] Couleurs hors-marque en dur (violet, ambre, hex) dans StatistiquesTab, RevisionTab, MuscleVolumePanel. Cassent One Voice + absentes en thème sombre. Fix : mapper sur tokens (--ring/--tertiary, --destructive/--warning/--success/--info). → /impeccable colorize.
- [P1] Vocabulaire de composants incohérent : RevisionTab construit boutons/inputs bruts au lieu de ui/Button, ui/Input. Fix : passer par les primitives. → /impeccable polish.
- [P2] Actions destructives sans garde-fou : ✕ fiche, suppression série/séance sans confirmation ni annulation. Fix : confirm inline ou toast Annuler. → /impeccable harden.
- [P2] Chargement/erreur incohérents : cœur = skeleton+retry ; RevisionTab = rien (échec silencieux). Fix : wrapper de fetch commun. → /impeccable harden.

## Persona Red Flags
Alex (power user) : bien servi (⌘K, j/k, densité, saisie rapide, minuteur). Manque suppression groupée de séries.
Sam (a11y/daltonien) : solide, mais couleurs hex/violet en dur ne basculent pas en thème sombre ; cibles ✕ minuscules. Bon point : statuts toujours doublés d'un label texte.

## Minor Observations
- Emojis comme iconographie (🎉 ⏱ ↩︎ 🔥 ⏳) vs lucide ailleurs → uniformiser.
- Double structure frontend/src/app + frontend/components : déroutant.
- StatistiquesTab heatmap : vérifier paliers ≥3:1.

## Questions to Consider
- À quoi ressemblerait Révision écrit uniquement avec Button/Input/Card + tokens sémantiques ?
- La notation Raté/Difficile/Bien/Facile doit-elle inventer 4 couleurs ou réutiliser l'échelle sémantique existante ?
