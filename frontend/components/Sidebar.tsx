"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home } from "lucide-react";
import { MODULES } from "@/lib/modules";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (slug: string) =>
    slug === "" ? pathname === "/" : pathname?.startsWith(`/${slug}`);

  return (
    <aside className="w-56 shrink-0 border-r border-[var(--border)] bg-[var(--muted)] px-3 py-6 hidden md:flex flex-col gap-0.5">
      <Link
        href="/"
        className="px-3 py-2 mb-3 text-sm font-semibold tracking-tight text-[var(--foreground)] hover:opacity-80 transition-opacity"
      >
        Mission Control
      </Link>

      <Link
        href="/"
        className={cn(
          "flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
          isActive("")
            ? "bg-[var(--background)] text-[var(--foreground)]"
            : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
        )}
      >
        <Home className="h-4 w-4 shrink-0" />
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
              "flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
              isActive(m.slug)
                ? "bg-[var(--background)] text-[var(--foreground)]"
                : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {m.label}
          </Link>
        );
      })}
    </aside>
  );
}
