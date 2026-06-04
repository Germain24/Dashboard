"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, X, Menu } from "lucide-react";
import { MODULE_GROUPS } from "@/lib/modules";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

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
      <header className="md:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between border-b border-[var(--border)] bg-[var(--background)]/95 backdrop-blur-sm px-4 h-12">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--foreground)] text-[var(--background)] text-[9px] font-bold shrink-0">
            MC
          </span>
          <span className="font-display text-base font-semibold tracking-tight">Mission Control</span>
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
            "relative z-10 w-72 bg-[var(--muted)] flex flex-col px-3 py-5 overflow-y-auto",
            "transition-transform duration-150 ease-out",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex items-center justify-between px-3 mb-4">
            <span className="font-display text-base font-semibold tracking-tight">Mission Control</span>
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

          {/* Modules groupés — même source et même ordre que la sidebar desktop. */}
          {MODULE_GROUPS.map((group) => (
            <div key={group.group}>
              <div className="mt-4 mb-1 px-3">
                <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--muted-foreground)]/60">
                  {group.group}
                </span>
              </div>
              <nav className="flex flex-col gap-0.5" aria-label={group.group}>
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
            </div>
          ))}
        </aside>
      </div>
    </>
  );
}
