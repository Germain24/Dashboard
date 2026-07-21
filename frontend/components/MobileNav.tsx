"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, X, Menu, ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { MODULE_GROUPS } from "@/lib/modules";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ThemeToggle";
import { DensityToggle } from "@/components/DensityToggle";
import { NotificationsWidget } from "@/components/layout/NotificationsWidget";
import { EASE_OUT, durations } from "@/lib/motion/tokens";

export function MobileNav() {
  const pathname = usePathname();
  const [openAtPath, setOpenAtPath] = useState<string | null>(null);
  const open = openAtPath === pathname;
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);

  const activeSlug = pathname?.split("/").filter(Boolean)[0];
  const activeGroup =
    MODULE_GROUPS.find((g) => g.items.some((m) => m.slug === activeSlug))?.group ?? null;
  const [openGroups, setOpenGroups] = useState<Set<string>>(() => new Set());
  const toggleGroup = (g: string) =>
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const trigger = triggerRef.current;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus());
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpenAtPath(null);
        return;
      }
      if (e.key !== "Tab" || !drawerRef.current) return;
      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled]), input:not([disabled]), " +
            "select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        ),
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, [open]);

  const isActive = (slug: string) =>
    slug === "" ? pathname === "/" : pathname?.startsWith("/" + slug);

  return (
    <>
      <header className="glass-panel md:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between border-b border-[var(--glass-border)] px-4 h-12">
        <Link href="/" className="flex items-center gap-2">
          <span className="font-display text-base tracking-tight">Mission Control</span>
        </Link>
        <button
          ref={triggerRef}
          type="button"
          data-ui-control
          onClick={() => setOpenAtPath(pathname)}
          aria-label="Ouvrir le menu"
          aria-expanded={open}
          aria-controls="mobile-nav-drawer"
          className="rounded-[var(--radius)] p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>
      </header>

      <div className="md:hidden h-12 shrink-0" aria-hidden="true" />

      <AnimatePresence>
        {open && (
          <motion.div
            id="mobile-nav-drawer"
            className="md:hidden fixed inset-0 z-40 flex"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: durations.fast, ease: EASE_OUT }}
          >
            <motion.button
              type="button"
              className="absolute inset-0 glass-veil h-full w-full cursor-default"
              onClick={() => setOpenAtPath(null)}
              aria-label="Fermer la navigation"
              tabIndex={-1}
            />

            <motion.aside
              ref={drawerRef}
              className="glass-modal relative z-10 flex w-72 flex-col overflow-y-auto rounded-r-[var(--radius-lg)] px-3 py-5"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: durations.base, ease: EASE_OUT }}
            >
              <div className="flex items-center justify-between px-3 mb-4">
                <span className="font-display text-base tracking-tight">Mission Control</span>
                <button
                  ref={closeRef}
                  type="button"
                  data-ui-control
                  onClick={() => setOpenAtPath(null)}
                  aria-label="Fermer le menu"
                  className="rounded-[var(--radius-sm)] p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>

              <nav className="flex flex-col gap-0.5" aria-label="Pages">
                <Link
                  href="/"
                  data-ui-control
                  aria-current={isActive("") ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
                    isActive("")
                      ? "nav-active font-medium"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
                  )}
                >
                  <Home className="h-4 w-4 shrink-0" aria-hidden="true" />
                  Accueil
                </Link>
              </nav>

              {/* Modules groupés repliables — même source que la sidebar desktop. */}
              {MODULE_GROUPS.map((group) => {
                const expanded = openGroups.has(group.group) || group.group === activeGroup;
                const hasActive = group.items.some((m) => m.slug === activeSlug);
                return (
                  <div key={group.group}>
                    <button
                      type="button"
                      data-ui-control
                      onClick={() => toggleGroup(group.group)}
                      aria-expanded={expanded}
                      className="mt-3 flex w-full items-center justify-between gap-2 rounded-[var(--radius)] px-3 py-1.5 font-display italic text-[13px] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
                    >
                      <span className="flex items-center gap-1.5">
                        {group.group}
                        {!expanded && hasActive && (
                          <span
                            className="h-1.5 w-1.5 rounded-full bg-[var(--ring)]"
                            aria-hidden="true"
                          />
                        )}
                      </span>
                      <ChevronRight
                        className={cn(
                          "h-3.5 w-3.5 shrink-0 transition-transform duration-150",
                          expanded && "rotate-90",
                        )}
                        aria-hidden="true"
                      />
                    </button>
                    {expanded && (
                      <nav className="mt-0.5 flex flex-col gap-0.5" aria-label={group.group}>
                        {group.items.map((m) => {
                          const Icon = m.icon;
                          const active = isActive(m.slug);
                          return (
                            <Link
                              key={m.slug}
                              href={"/" + m.slug}
                              data-ui-control
                              aria-current={active ? "page" : undefined}
                              className={cn(
                                "flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
                                active
                                  ? "nav-active font-medium"
                                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
                              )}
                            >
                              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                              <span className="flex-1 min-w-0 truncate">{m.label}</span>
                            </Link>
                          );
                        })}
                      </nav>
                    )}
                  </div>
                );
              })}
              <div className="mt-auto flex items-center gap-2 border-t border-[var(--glass-border)] px-2 pt-4">
                <NotificationsWidget />
                <DensityToggle />
                <ThemeToggle />
              </div>
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
