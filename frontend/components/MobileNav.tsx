"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { Menu, Search } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { usePathname } from "next/navigation";
import { MODULE_GROUPS } from "@/lib/modules";
import { MobileNavDrawer, useMobileDrawerLifecycle } from "@/components/MobileNavParts";
import { HealthBadge } from "@/components/HealthBadge";

export function MobileNav() {
  const pathname = usePathname();
  const [openAtPath, setOpenAtPath] = useState<string | null>(null);
  const open = openAtPath === pathname;
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const [openGroups, setOpenGroups] = useState<Set<string>>(() => new Set());
  const activeSlug = pathname?.split("/").filter(Boolean)[0];
  const activeGroup = findActiveGroup(activeSlug);
  const close = useCallback(() => setOpenAtPath(null), []);
  const openMenu = useCallback(() => setOpenAtPath(pathname), [pathname]);
  const toggleGroup = useCallback(
    (group: string) => setOpenGroups((previous) => toggleGroupState(previous, group)),
    [],
  );
  useMobileDrawerLifecycle(open, drawerRef, triggerRef, closeRef, close);

  return (
    <>
      <header className="glass-panel md:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between border-b border-[var(--glass-border)] px-4 h-12">
        <Link href="/" className="flex items-center gap-2">
          <span className="font-display text-base tracking-tight">Mission Control</span>
        </Link>
        <div className="flex items-center gap-1">
          <HealthBadge compact />
          <button
            type="button"
            data-ui-control
            onClick={() => window.dispatchEvent(new CustomEvent("mc:command-palette"))}
            aria-label="Rechercher une page ou une donnée"
            title="Rechercher dans Mission Control"
            className="rounded-[var(--radius)] p-1.5 text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Search className="h-5 w-5" aria-hidden="true" />
          </button>
          <button
            ref={triggerRef}
            type="button"
            data-ui-control
            onClick={openMenu}
            aria-label="Ouvrir le menu"
            aria-expanded={open}
            aria-controls="mobile-nav-drawer"
            className="rounded-[var(--radius)] p-1.5 text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>
      {pathname !== "/" && <div className="h-12 shrink-0 md:hidden" aria-hidden="true" />}
      <AnimatePresence>
        {open && (
          <MobileNavDrawer
            pathname={pathname}
            activeSlug={activeSlug}
            activeGroup={activeGroup}
            openGroups={openGroups}
            toggleGroup={toggleGroup}
            close={close}
            drawerRef={drawerRef}
            closeRef={closeRef}
          />
        )}
      </AnimatePresence>
    </>
  );
}

function findActiveGroup(activeSlug: string | undefined): string | null {
  return (
    MODULE_GROUPS.find((group) => group.items.some((module) => module.slug === activeSlug))
      ?.group ?? null
  );
}

function toggleGroupState(previous: Set<string>, group: string): Set<string> {
  const next = new Set(previous);
  if (next.has(group)) next.delete(group);
  else next.add(group);
  return next;
}
