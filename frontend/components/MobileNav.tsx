"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, X, Menu } from "lucide-react";
import { MODULES } from "@/lib/modules";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Ferme le drawer quand on navigue
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const isActive = (slug: string) =>
    slug === "" ? pathname === "/" : pathname?.startsWith(`/${slug}`);

  return (
    <>
      {/* ── Barre supérieure mobile ──────────────────────── */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between border-b border-[var(--border)] bg-[var(--background)] px-4 h-12">
        <span className="text-sm font-semibold tracking-tight">
          Mission Control
        </span>
        <button
          onClick={() => setOpen(true)}
          aria-label="Ouvrir le menu"
          className="rounded-[var(--radius)] p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {/* ── Spacer pour compenser la barre fixe ─────────── */}
      <div className="md:hidden h-12 shrink-0" aria-hidden />

      {/* ── Overlay + Drawer ─────────────────────────────── */}
      {open && (
        <div
          className="md:hidden fixed inset-0 z-40 flex"
          role="dialog"
          aria-modal
          aria-label="Navigation"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          {/* Drawer */}
          <aside className="relative z-10 w-64 bg-[var(--muted)] flex flex-col gap-1 px-3 py-6 overflow-y-auto">
            <div className="flex items-center justify-between px-3 mb-3">
              <span className="text-sm font-semibold tracking-tight">Mission Control</span>
              <button
                onClick={() => setOpen(false)}
                aria-label="Fermer le menu"
                className="rounded-[var(--radius-sm)] p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <Link
              href="/"
              className={cn(
                "flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
                isActive("")
                  ? "bg-[var(--background)] text-[var(--foreground)] shadow-sm"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
              )}
            >
              <Home className="h-4 w-4" />
              Accueil
            </Link>

            <div className="my-2 h-px bg-[var(--border)]" />

            {MODULES.map((m) => {
              const Icon = m.icon;
              return (
                <Link
                  key={m.slug}
                  href={`/${m.slug}`}
                  className={cn(
                    "flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
                    isActive(m.slug)
                      ? "bg-[var(--background)] text-[var(--foreground)] shadow-sm"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {m.label}
                </Link>
              );
            })}
          </aside>
        </div>
      )}
    </>
  );
}
