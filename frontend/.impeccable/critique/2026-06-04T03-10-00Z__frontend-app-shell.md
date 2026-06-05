---
target: whole app shell
total_score: 35
p0_count: 0
p1_count: 0
timestamp: 2026-06-04T03-10-00Z
slug: frontend-app-shell
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Active nav now reads (blue); health/breadcrumbs/today states all present; misleading progress bar gone |
| 2 | Match System / Real World | 4 | French, real module names, "Aujourd'hui / À faire / État du jour" |
| 3 | User Control and Freedom | 3 | Esc + focus-restore everywhere; but mark-done has no undo if misclicked |
| 4 | Consistency and Standards | 4 | Single nav source; sidebar = mobile = palette; one shared active-state + modal pattern; DESIGN.md matches reality |
| 5 | Error Prevention | 3 | Optimistic mark-done reverts on failure; little destructive surface; no confirm on mark-done |
| 6 | Recognition Rather Than Recall | 3 | ⌘K now visible + labeled nav + `?` help; but j/k still only inside the help modal, ⌘K is desktop-only |
| 7 | Flexibility and Efficiency | 4 | ⌘K, j/k, density toggle, inline mark-done — strong power-user layer |
| 8 | Aesthetic and Minimalist Design | 4 | Progress bar + identical grid gone; status board is focused; version string quieted to "OK" |
| 9 | Error Recovery | 3 | TodayPanel retry, HealthBadge offline detail, mark-done toast+revert; messages calm but not deeply diagnostic |
| 10 | Help and Documentation | 3 | Shortcuts cheatsheet (`?`) is discoverable and good; no per-feature/contextual help beyond it |
| **Total** | | **35/40** | **Good (top of band) — the load-bearing wall is fixed** |

## Anti-Patterns Verdict

**Does this look AI-generated? No, and now less than before.** The two biggest tells from the first pass are gone: the permanent-100% progress bar and the 12-cell identical-card grid. The home is a focused status board built on real data; the nav is one coherent system; the active state is a deliberate blue. The deterministic detector scanned 11 shell/home files and returned **zero** hits (no gradient text, side-stripes, glassmorphism, hero-metric template). 

Residual mild tells: the sidebar still carries five `uppercase tracking-wider` group labels (defensible as nav grouping, but it's a lot of tracked uppercase), and the "État du jour" signal strip is four same-shaped chips (saved from the identical-grid ban only because the data inside genuinely varies). Neither is a defect; both are worth an eye.

No browser overlay was produced (this environment has no browser-automation tool); the clean CLI scan is the Assessment-B evidence.

## Overall Impression

This is a different interface from the 29/40 one. The single most expensive problem, three navigation surfaces disagreeing about themselves, is gone, and with it the "where am I" ambiguity, the hidden power-user layer, and the dead-weight home. What's left is genuinely minor: small recovery/affordance polish, not structural work. The shell now does what PRODUCT.md asks ("consistency is the feature," "status in seconds").

## What's Working

1. **The navigation is now one system.** `lib/modules.ts` drives sidebar, mobile drawer, and palette; Robot and Jobs are reachable everywhere; the dead second sidebar is deleted. This is the fix that moved the score most (Consistency 2 → 4).
2. **"You are here" finally reads, and the affordances are visible.** The blue `.nav-active` (wash + AA-safe blue + `aria-current`) replaced the invisible gray, and ⌘K / `?` are now surfaced instead of secret. Recognition and Visibility both climbed.
3. **The home earns its space.** A real "Aujourd'hui" panel (schedule + actionable tasks) with full loading/error/empty states, plus a varied signal strip, instead of a frozen progress bar over identical tiles.

## Priority Issues

There are **no P0 or P1 issues** this pass. The remaining items are P2/P3 polish.

### [P2] Mark-done is a one-way action with no undo
- **Why it matters:** Tapping the circle on an urgent task optimistically removes it and marks it done server-side. A misclick (easy on the compact rows) means the task silently vanishes from home with no on-the-spot undo; recovery means going to /agenda. For the app's one user, that's a small but real trust ding.
- **Fix:** On mark-done, fire a sonner toast with an **Annuler** action (you already use sonner; the success path currently shows nothing). Re-insert the task and call a reopen endpoint on undo, or simply delay the API call until the toast dismisses.
- **Suggested command:** `/impeccable harden`

### [P3] j/k and mobile search remain partly hidden
- **Why it matters:** `j`/`k` are only learnable by opening the `?` sheet, and the ⌘K trigger is desktop-only, so on mobile there's no search at all (only the drawer). Fine for 12 modules today; a ceiling as the app grows.
- **Fix:** Consider a small search affordance in the mobile drawer header, and a one-time hint or a visible `j/k` cue. Low priority.
- **Suggested command:** `/impeccable onboard`

## Persona Red Flags

**Alex (Power User):** Now well served. ⌘K is visible, the palette traps focus, j/k work, Robot is reachable from the sidebar, and inline mark-done lets him clear tasks from home. Only nit: no undo on a fat-fingered mark-done.

**Sam (Accessibility):** The two prior blockers are resolved: skip-to-content link is the first focusable element, and the icon-only rail is gone (labels show from `md`). Both modals (palette + shortcuts) now trap focus and restore it. Remaining: verify the blue active state and signal-chip text hold 4.5:1 in both themes (the active token was computed to pass; the chips inherit foreground/muted, which do).

**Riley (Stress Tester):** The nav divergence he found is gone (one source of truth). The `duration-[var(--transition)]` invalid-CSS bug is fixed. New probe: at 22:00 with all of today's events past, the panel shows "Rien de prévu aujourd'hui" even though events happened earlier, the copy slightly overclaims an empty day.

## Minor Observations

- **Dead code:** `NotificationsWidget` (the bell popover) is now mounted nowhere yet still exported from `components/layout/index.ts`. Either wire it into the shell (it would strengthen the status-board story) or delete it.
- **Empty-state copy:** "Rien de prévu aujourd'hui" fires when there are no *upcoming* events; if the day had earlier events, "Plus rien à venir aujourd'hui" is more accurate.
- **Sidebar group labels** are five `uppercase tracking-wider` strings; consider sentence-case or lighter treatment if you want to fully retire the tracked-uppercase reflex.
- **Signal chips** read as clickable mainly on hover (border tint); a persistent affordance (a faint chevron, or a clearer hover) would help discoverability.

## Questions to Consider

- The bell (`NotificationsWidget`) is built but unmounted, and you chose "Today only" for the home. Is a notifications surface still wanted somewhere, or should it be deleted?
- Should mark-done stay instant (fast, power-user) or gain an undo affordance (safer)? It's the one place on the board where a misclick has a consequence.
- Is the four-signal "État du jour" set the right one, or would training/budget signals earn a place over Lecture?
