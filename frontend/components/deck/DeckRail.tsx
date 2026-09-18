"use client";

/**
 * Navigation cinématique du Deck : un seul rail DOM, horizontal sur mobile et
 * vertical sur desktop. La capsule active glisse entre les sections et expose
 * toujours un libellé textuel — la couleur n'est jamais le seul repère.
 */

import { useEffect, useId, useRef, type CSSProperties } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";
import { durations, EASE_OUT, springs } from "@/lib/motion/tokens";

export function DeckRail({
  total,
  active,
  labels,
  onJump,
}: {
  total: number;
  active: number;
  labels: string[];
  onJump: (i: number) => void;
}) {
  const reduced = useReducedMotion();
  const railId = useId();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const activeButtonRef = useRef<HTMLButtonElement>(null);
  const current = Math.max(0, Math.min(active, Math.max(0, total - 1)));
  const progress = total <= 1 ? 0 : current / (total - 1);
  const railStyle = {
    "--deck-rail-progress": progress,
    "--deck-rail-label-top": `${1.625 + current * 2.75}rem`,
  } as CSSProperties;
  const layoutTransition = reduced ? { duration: 0 } : springs.soft;

  // Avec huit sections, la capsule active peut dépasser la largeur d'un
  // téléphone. On ne fait défiler que le rail, jamais le Deck lui-même.
  useEffect(() => {
    const scroller = scrollerRef.current;
    const button = activeButtonRef.current;
    if (!scroller || !button || scroller.scrollWidth <= scroller.clientWidth) return;

    const left = button.offsetLeft + button.offsetWidth / 2 - scroller.clientWidth / 2;
    scroller.scrollTo?.({
      left: Math.max(0, left),
      behavior: reduced ? "auto" : "smooth",
    });
  }, [current, reduced]);

  if (total <= 0) return null;

  return (
    <nav
      className="fixed inset-x-0 bottom-20 z-[var(--z-sidebar)] flex justify-center px-1 md:inset-x-auto md:bottom-auto md:right-4 md:top-1/2 md:-translate-y-1/2 md:justify-end md:px-0"
      aria-label="Navigation des sections du tableau de bord"
      style={railStyle}
    >
      <AnimatePresence mode="popLayout">
        <motion.div
          key={current}
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reduced ? undefined : { opacity: 0 }}
          transition={reduced ? { duration: 0 } : { duration: durations.fast, ease: EASE_OUT }}
          className="glass-panel absolute bottom-[calc(100%+0.5rem)] left-1/2 flex -translate-x-1/2 items-baseline gap-1.5 whitespace-nowrap rounded-[var(--radius-full)] border border-[var(--glass-border)] px-3 py-1.5 shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-sm)] md:bottom-auto md:left-auto md:right-[calc(100%+0.55rem)] md:top-[var(--deck-rail-label-top)] md:-translate-y-1/2 md:translate-x-0 md:py-2"
          aria-hidden="true"
        >
          <span className="max-w-48 truncate text-xs font-semibold">
            {labels[current] || `Section ${current + 1}`}
          </span>
          <span className="font-mono text-[10px] tabular-nums text-[var(--muted-foreground)]">
            {String(current + 1).padStart(2, "0")}/{String(total).padStart(2, "0")}
          </span>
        </motion.div>
      </AnimatePresence>

      <div
        ref={scrollerRef}
        className="glass-panel no-scrollbar max-w-[calc(100vw-0.5rem)] overflow-x-auto rounded-[var(--radius-full)] border border-[var(--glass-border)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-md)] md:w-14 md:max-w-none md:overflow-visible"
      >
        <div className="relative flex w-max items-center p-1 md:w-14 md:flex-col">
          {/* Rail neutre puis portion déjà parcourue. Le même élément pivote
              via les classes responsive : pas de duplication desktop/mobile. */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-6 right-6 top-1/2 h-px bg-[color-mix(in_srgb,var(--muted-foreground)_22%,transparent)] md:bottom-7 md:left-auto md:right-7 md:top-7 md:h-auto md:w-px"
          />
          <span
            aria-hidden="true"
            data-testid="deck-rail-progress"
            style={{ "--deck-rail-progress": progress } as CSSProperties}
            className={cn(
              "pointer-events-none absolute left-6 right-6 top-1/2 h-px origin-left bg-[color-mix(in_srgb,var(--ring)_58%,transparent)]",
              "[transform:scaleX(var(--deck-rail-progress))]",
              "md:bottom-7 md:left-auto md:right-7 md:top-7 md:h-auto md:w-px md:origin-top md:[transform:scaleY(var(--deck-rail-progress))]",
              !reduced && "transition-transform duration-300 ease-[var(--ease-out)]",
            )}
          />

          {Array.from({ length: total }).map((_, i) => {
            const isActive = i === current;
            const label = labels[i] || `Section ${i + 1}`;

            return (
              <motion.button
                ref={isActive ? activeButtonRef : undefined}
                key={i}
                layout={!reduced}
                initial={false}
                transition={layoutTransition}
                type="button"
                onClick={() => onJump(i)}
                aria-current={isActive ? "true" : undefined}
                aria-label={`${label}, section ${i + 1} sur ${total}${isActive ? ", actuelle" : ""}`}
                title={label}
                className={cn(
                  "group relative isolate inline-flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center overflow-visible rounded-[var(--radius-full)] border border-transparent",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]",
                  isActive
                    ? "text-[var(--foreground)]"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
                )}
              >
                {isActive && (
                  <motion.span
                    layoutId={reduced ? undefined : `${railId}-active`}
                    transition={layoutTransition}
                    aria-hidden="true"
                    className="absolute inset-0 -z-10 rounded-[var(--radius-full)] border border-[color-mix(in_srgb,var(--ring)_22%,var(--glass-border))] bg-[var(--glass-strong)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-sm)]"
                  />
                )}

                <span
                  aria-hidden="true"
                  className={cn(
                    "relative z-10 block shrink-0 rounded-full transition-colors duration-200",
                    isActive
                      ? "h-2.5 w-2.5 bg-[var(--ring)] shadow-[0_0_0_3px_color-mix(in_srgb,var(--ring)_12%,transparent)]"
                      : "h-2 w-2 bg-[color-mix(in_srgb,var(--muted-foreground)_45%,transparent)] group-hover:bg-[var(--muted-foreground)]",
                  )}
                />
              </motion.button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
