"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, X, Menu, ChevronRight } from "lucide-react";
import { MODULE_GROUPS } from "@/lib/modules";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  const activeSlug = pathname?.split("/").filter(Boolean)[0];
  const activeGroup =
    MODULE_GROUPS.find((g) => g.items.some((m) => m.slug === activeSlug))?.group ?? null;
  const [openGroups, setOpenGroups] = useState<Set<string>>(
    () => new Set(activeGroup ? [activeGroup] : []),
  );
  useEffect(() => {
    if (activeGroup)
      setOpenGroups((prev) => (prev.has(activeGroup) ? prev : new Set(prev).add(activeGroup)));
  }, [activeGroup]);
  const toggleGroup = (g: string) =>
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });

  useEffect(() => { setOpen(false); }, [pathname]);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
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
          onClick={() => setOpen(true)}
          aria-label="Ouvrir le menu"
          aria-expanded={open}
          aria-controls="mobile-nav-drawer"
          className="rounded-[var(--radius)] p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      <div className="md:hidden h-12 shrink-0" aria-hidden="true" />

      <div
        id="mobile-nav-drawer"
        className={cn(
          "md:hidden fixed inset-0 z-40 flex",
          "transition-opacity duration-150",
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        )}
        role="dialog"
        aria-modal={true}
        aria-label="Navigation"
        aria-hidden={!open}
      >
        <div
          className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />

        <aside
          className={cn(
            "glass-modal relative z-10 w-72 flex flex-col px-3 py-5 overflow-y-auto rounded-r-[var(--radius-lg)]",
            "transition-transform duration-200 ease-[var(--ease-out)]",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex items-center justify-between px-3 mb-4">
            <span className="font-display text-base tracking-tight">Mission Control</span>
            <button
              ref={closeRef}
              onClick={() => setOpen(false)}
              aria-label="Fermer le menu"
              className="rounded-[var(--radius-sm)] p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <nav className="flex flex-col gap-0.5" aria-label="Pages">
            <Link
              href="/"
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
            const expanded = openGroups.has(group.group);
            const hasActive = group.items.some((m) => m.slug === activeSlug);
            return (
              <div key={group.group}>
                <button
                  type="button"
                  onClick={() => toggleGroup(group.group)}
                  aria-expanded={expanded}
                  className="mt-3 flex w-full items-center justify-between gap-2 rounded-[var(--radius)] px-3 py-1.5 font-display italic text-[13px] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
                >
                  <span className="flex items-center gap-1.5">
                    {group.group}
                    {!expanded && hasActive && (
                      <span className="h-1.5 w-1.5 rounded-full bg-[var(--ring)]" aria-hidden="true" />
                    )}
                  </span>
                  <ChevronRight
                    className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-150", expanded && "rotate-90")}
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
        </aside>
      </div>
    </>
  );
}
