"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home } from "lucide-react";
import { MODULES } from "@/lib/modules";
import { cn } from "@/lib/utils";

interface NavItemProps {
  href: string;
  active: boolean;
  children: React.ReactNode;
}

function NavItem({ href, active, children }: NavItemProps) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2 text-sm",
        "transition-colors duration-150",
        active
          ? "bg-[var(--background)] text-[var(--foreground)] font-medium shadow-sm"
          : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
      )}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full bg-[var(--ring)]"
        />
      )}
      {children}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (slug: string) =>
    slug === "" ? pathname === "/" : pathname?.startsWith("/" + slug);

  return (
    <aside
      className="w-56 shrink-0 border-r border-[var(--border)] bg-[var(--muted)] px-3 py-5 hidden md:flex flex-col"
      aria-label="Navigation principale"
    >
      <Link href="/" className="flex items-center gap-2 px-3 py-2 mb-4 group">
        <span className="flex h-6 w-6 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--foreground)] text-[var(--background)] text-[10px] font-bold shrink-0 transition-opacity group-hover:opacity-80">
          MC
        </span>
        <span className="text-sm font-semibold tracking-tight transition-opacity group-hover:opacity-80">
          Mission Control
        </span>
      </Link>

      <nav className="flex flex-col gap-0.5" aria-label="Pages">
        <NavItem href="/" active={isActive("")}>
          <Home className="h-4 w-4 shrink-0" aria-hidden="true" />
          Accueil
        </NavItem>
      </nav>

      <div className="mt-4 mb-1 px-3">
        <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--muted-foreground)]/60">
          Modules
        </span>
      </div>

      <nav className="flex flex-col gap-0.5 flex-1 overflow-y-auto" aria-label="Modules">
        {MODULES.map((m) => {
          const Icon = m.icon;
          return (
            <NavItem key={m.slug} href={"/" + m.slug} active={isActive(m.slug)}>
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="flex-1 min-w-0 truncate">{m.label}</span>
              {!m.ready && (
                <span
                  aria-label="A venir"
                  className="h-1 w-1 rounded-full bg-[var(--border)] shrink-0"
                />
              )}
            </NavItem>
          );
        })}
      </nav>
    </aside>
  );
}
