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
    <aside className="w-60 shrink-0 border-r border-[var(--border)] bg-[var(--muted)] px-3 py-6 hidden md:flex flex-col gap-1">
      <Link
        href="/"
        className="px-3 py-2 mb-3 text-lg font-semibold tracking-tight animate-fade-in block"
      >
        Mission Control
      </Link>

      <Link
        href="/"
        className={cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm interactive transition-all duration-200",
          isActive("")
            ? "nav-active font-medium"
            : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
        )}
      >
        <Home className="h-4 w-4 transition-colors duration-200" />
        Accueil
      </Link>

      <div className="my-3 h-px bg-[var(--border)]" />

      <nav className="flex flex-col gap-0.5 stagger">
        {MODULES.map((m) => {
          const Icon = m.icon;
          return (
            <Link
              key={m.slug}
              href={`/${m.slug}`}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm interactive transition-all duration-200",
                isActive(m.slug)
                  ? "nav-active font-medium"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
              )}
            >
              <Icon className="h-4 w-4 transition-colors duration-200" />
              {m.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
