# Product

## Register

product

## Users

A single user: the builder/owner. This is a personal "Mission Control" dashboard used daily to run one person's life and studies (études, finance, budget, agenda, santé, entraînement, habitudes, and more). The user is also the developer, so they are an expert in their own tool: no onboarding, no hand-holding, no marketing surface. They open it to check status fast and act, often returning to the same modules many times a day. Context is a laptop primarily, phone secondarily. UI language is French.

## Product Purpose

Give one person a single, fast, trustworthy cockpit over every recurring area of their life. Each module answers "what's my status and what should I do next?" without ceremony. Success looks like: the user glances at a module, understands their state in seconds, and acts (log a session, check a deadline, mark a habit) with minimal friction. The app earns trust by being consistent, current (freshness signals), and never making the user re-derive information the system already knows.

## Brand Personality

Calm, focused, precise. The voice of a quiet instrument, not a coach and not a corporate SaaS. Restraint over decoration: Notion / Bear / iA Writer lineage (already encoded in DESIGN.md as "Minimal Mono + Blue accent"). Confidence through clarity, not through loud color or persuasion copy. Personality shows in precise typography, honest status, and a single deliberate blue accent, not in illustrations or playful flourishes.

## Anti-references

- **Marketing-SaaS dashboards**: gradient hero metrics, big "+12% this week" cards with confetti, persuasion copy. This is a tool, not a pitch.
- **Gamified habit apps** (Duolingo-style): mascots, aggressive streaks-as-pressure, badges, celebratory modals. Streaks can inform but must not nag.
- **Cluttered "everything visible" admin panels**: dense grids of identical cards with no hierarchy, where nothing is more important than anything else.
- **Generic AI-template look**: tiny uppercase tracked eyebrows on every section, identical icon+heading+text card grids, decorative glassmorphism.

## Design Principles

1. **Status in seconds.** Every module's primary job is to communicate current state at a glance before any interaction. Lead with the answer, not the controls.
2. **One accent, earned.** Blue means "interactive / focus / current" and nothing else. Color is a signal, never decoration. Semantic colors (success/warning/destructive) only carry real meaning.
3. **Consistency is the feature.** A single user across a dozen modules learns one set of patterns once (header + tabs + content, the same primitives). Divergence between modules is a bug.
4. **Quiet by default, precise on demand.** Show what's needed now; reveal depth progressively. Density is fine for an expert, but it must be ordered density, not noise.
5. **Honest and current.** Freshness, loading, empty, and error states are first-class. Never show stale data as if it were live; never leave the user guessing whether an action worked.

## Accessibility & Inclusion

Target WCAG AA (already stated in DESIGN.md). Body text ≥ 4.5:1, large text ≥ 3:1, touch targets ≥ 36px. Full keyboard operability (this is a power-user tool: keyboard-first matters). Visible focus rings via `:focus-visible`. Respect `prefers-color-scheme` for dark/light. Motion, when added, must honor `prefers-reduced-motion`. Meaning must never be carried by color alone.
