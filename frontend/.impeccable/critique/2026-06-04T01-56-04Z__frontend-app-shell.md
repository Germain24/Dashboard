---
target: whole app shell
total_score: 29
p0_count: 0
p1_count: 3
timestamp: 2026-06-04T01-56-04Z
slug: frontend-app-shell
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Active-nav state is near-invisible in light mode; home progress bar is permanently 100% |
| 2 | Match System / Real World | 4 | French labels, real-world module names, natural order |
| 3 | User Control and Freedom | 3 | Esc + breadcrumbs + persisted reorder; no undo for reorder (low stakes) |
| 4 | Consistency and Standards | 2 | Two desktop sidebars (one dead); desktop nav ≠ mobile nav ≠ home grid (different items, icons, order) |
| 5 | Error Prevention | 3 | Backend-down surfaced; little destructive surface to guard |
| 6 | Recognition Rather Than Recall | 2 | ⌘K palette + j/k shortcuts are invisible; md-rail is icon-only with no labels |
| 7 | Flexibility and Efficiency | 4 | Command palette, keyboard shortcuts, drag-reorder, density toggle — genuinely strong |
| 8 | Aesthetic and Minimalist Design | 3 | Clean and on-brand; permanent progress bar + version string are noise |
| 9 | Error Recovery | 3 | HealthBadge error state with detail; app-level error/not-found exist |
| 10 | Help and Documentation | 2 | Palette documents its own keys, but j/k and ⌘K have no global discoverability |
| **Total** | | **29/40** | **Good — solid foundation, consistency is the weak load-bearing wall** |

## Anti-Patterns Verdict

**Does this look AI-generated? Mostly no.** This reads as a real, opinionated personal tool: a committed minimal-mono + single-blue-accent system, French throughout, power-user affordances (⌘K, j/k, drag-reorder, density toggle) that templates don't ship. The deterministic detector scanned 11 shell files and returned **zero** slop hits (no gradient text, no side-stripe borders, no glassmorphism). The restraint is earned, not generic.

Two mild tells remain: (1) the home page uses two `text-xs uppercase tracking-widest` section eyebrows ("Aujourd'hui", "Modules"), and the desktop sidebar adds five more uppercase group labels — that's a lot of tracked uppercase for one viewport; (2) the home "Modules" area is a 12-cell identical-card grid (icon + label + description, all same size), which is the launcher version of the banned identical-card-grid. Neither sinks the page, but both are reflexes worth interrogating.

No browser overlay was produced: this environment has no browser-automation tool, so the live-page injection step was skipped. The deterministic CLI scan is the Assessment-B evidence, and it was clean.

## Overall Impression

The visual layer is genuinely good and the personality is real. The problem isn't how it looks; it's that the **navigation has three different opinions about itself**, and that quietly undermines the one principle this app lives or dies on — "consistency is the feature" for a single user crossing a dozen modules. Fix the navigation model and this jumps to the mid-30s.

## What's Working

1. **Power-user layer is the real differentiator.** Command palette (⌘K), j/k shortcuts, drag-to-reorder with localStorage persistence, and a density toggle — for a single expert user, this is exactly right and it's the hardest part to fake. Heuristic 7 scores a true 4.
2. **The color system is disciplined.** One blue accent that means "interactive/focus/current," honest semantic colors, full dark/light via tokens with an anti-flash script. No hardcoded hex leaking into components. This is the "one accent, earned" principle actually held.
3. **States are taken seriously.** HealthBadge has loading/ok/error with `aria-live` and detail-on-hover; TodayAgenda self-hides when empty rather than showing a dead shell; reduced-motion is globally honored. First-class states are rare and they're here.

## Priority Issues

### [P1] The navigation model contradicts itself across surfaces
- **Why it matters:** The live desktop sidebar (`components/layout/Sidebar.tsx`) is grouped into 5 categories, **omits Robot**, and **adds Jobs**. The mobile drawer (`MobileNav.tsx`) is a flat list from `lib/modules.ts` that **includes Robot** and **omits Jobs**, in a different order. The home grid is a third order again. So the AI-chat module is unreachable from the desktop sidebar, Jobs is unreachable from mobile, and "where things live" changes when you rotate your phone. For a single user who is supposed to learn one map once, this is the most expensive kind of friction. It also directly violates your stated principle "consistency is the feature."
- **Fix:** Make `lib/modules.ts` the single source of truth for nav (slug, label, icon, group, ready). Derive the sidebar, the mobile drawer, the home grid, **and** the command palette from it. Decide once whether Robot and Jobs are first-class nav items and apply that everywhere.
- **Suggested command:** `/impeccable harden`

### [P1] Two desktop Sidebar components exist; one is dead code
- **Why it matters:** `components/Sidebar.tsx` (flat list, blue `nav-active` glow, has an "Accueil" item, `w-60`) is **not imported anywhere** — `layout.tsx` pulls `Sidebar` from `@/components/layout`. So the sidebar you'd read first is a decoy, and the documented blue active-state lives only in the dead file. Anyone (including future-you) editing the obvious file changes nothing. This is also why the active state in the real sidebar is a faint gray, not the blue the design system promises.
- **Fix:** Delete `components/Sidebar.tsx`. Port the one thing it does better (the blue `nav-active` treatment, and an explicit Accueil entry) into the live `components/layout/Sidebar.tsx`.
- **Suggested command:** `/impeccable harden`

### [P1] "Where am I" is too quiet, and the md rail is unlabeled
- **Why it matters:** In light mode the active item is `bg-[var(--accent)]` (#f5f5f5) sitting on `bg-[var(--sidebar)]` (#f9f9fb) — two near-identical off-whites, so the current-page highlight is almost invisible. Worse, between 768–1023px the sidebar collapses to a 64px icon-only rail (`md:w-16`) with **no visible labels and no group headings** — 13 similar lucide glyphs (Target, Heart, Dumbbell, Sparkles…) distinguishable only by `title` tooltips, which screen readers and touch users don't get. A first-timer or anyone on a small laptop is reading hieroglyphs.
- **Fix:** Use the blue `nav-active` style (inset blue bar + tinted bg) for the active item in both modes so location reads at a glance. For the rail, either show labels earlier, or drop the icon-only tier and go straight from hidden→full, or add a persistent text label under each icon.
- **Suggested command:** `/impeccable colorize` (active state) + `/impeccable adapt` (rail breakpoint)

### [P2] Power-user features are invisible until you already know them
- **Why it matters:** ⌘K and the j/k shortcuts are the best things here, and nothing on screen hints they exist. The command palette only documents its keys *after* you've opened it. Recognition-over-recall fails: the affordance helps exactly the user who needs it least.
- **Fix:** Add a small, always-visible `⌘K` hint (a faint pill in the sidebar footer or a search-shaped button that opens the palette). Surface j/k in a tiny keyboard-shortcuts reference (you already have a `KeyboardShortcuts` component mounted — give it a visible entry point, e.g. `?`).
- **Suggested command:** `/impeccable onboard`

### [P2] The home "build progress" bar is now permanently full
- **Why it matters:** Every module in `lib/modules.ts` is `ready: true`, so the header reads "12 modules actifs · 0 à venir" with a progress bar pinned at 100% forever. It was meaningful during build-out; now it's a UI element that can never change state — visual noise that fails "honest and current." The 12-cell identical grid underneath has no hierarchy either: Finance (rich, Buffett scoring) looks identical to Skincare.
- **Fix:** Drop the progress bar (the build is done), or repurpose that space for something live — e.g. count of modules with attention/alerts today. For the grid, let `LiveModuleStat` or an "needs attention" signal drive subtle differentiation instead of 12 equal tiles.
- **Suggested command:** `/impeccable distill`

## Persona Red Flags

**Alex (Power User):** Mostly delighted — ⌘K, j/k, drag-reorder, density toggle are exactly his tools. But he can't reach the AI-chat (Robot) module from the desktop sidebar at all, and the active-page highlight is so faint he loses his place when alt-tabbing back. The j/k shortcuts he'd love are undiscoverable; he only finds them by reading source.

**Sam (Accessibility / keyboard + screen reader):** Two real blockers. (1) **No skip-to-content link** — every page forces a tab through ~13 sidebar links + breadcrumb before reaching `<main>`. (2) The 768–1023px icon-only rail conveys destination by `title` tooltip alone; screen readers get the link text but sighted keyboard users at that width get no visible labels. The command palette is `role="dialog"` but doesn't trap focus, so Tab escapes the modal into the page behind it.

**Riley (Stress Tester):** Immediately finds the nav divergence — adds Robot to the desktop URL bar, notices it's missing from the sidebar, then sees it reappear on mobile. Reorders the grid, reloads, confirms it persists (good), then asks why the order doesn't match the sidebar (which isn't reorderable). Notices `duration-[var(--transition)]` on the HealthBadge resolves to "150ms ease" — an invalid CSS duration, so that transition silently doesn't run.

## Minor Observations

- **Font drift / perf:** `globals.css` loads Plus Jakarta Sans via a render-blocking `@import url(fonts.googleapis…)`, while DESIGN.md still claims "system-ui, zero latence." Pick one; if you keep Jakarta, load it via `next/font` to kill the blocking request and layout shift.
- **Icon drift:** the sidebar uses different lucide icons than the home grid for the same destinations (Target vs ListTodo for Habitudes, Heart vs HeartPulse, TrendingUp vs LineChart, CreditCard vs Wallet). Same place, two faces.
- **Stale design doc:** DESIGN.md says "no manual theme toggle (V1)" and `--sidebar-width: 224px`, but you now ship Theme + Density toggles and a `w-60` (240px) sidebar. Refresh DESIGN.md so it stops lying to the next change.
- **HealthBadge** shows a raw backend version string (`v1.2.3`) to a single user — fine as honest status, but the dot + "OK" alone would be calmer and more on-brand.

## Questions to Consider

- If the build-out is finished, what is the home screen *for* now — a launcher, or a status board? A status board would justify killing the progress bar and the identical grid in favor of "what needs me today."
- Should Robot and Jobs be peers of the other modules, or genuinely a different tier? Answering that once kills the nav divergence at the root.
- What would a confident version of "you are here" look like in this sidebar — and why is it currently whispering?
