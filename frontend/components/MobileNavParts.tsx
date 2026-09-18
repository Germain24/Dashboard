import { useEffect, type RefObject } from "react";
import Link from "next/link";
import { Home, X, ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { GROUP_LABELS, MODULE_GROUPS } from "@/lib/modules";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ThemeToggle";
import { DensityToggle } from "@/components/DensityToggle";
import { NotificationsWidget } from "@/components/layout/NotificationsWidget";
import { EASE_OUT, durations } from "@/lib/motion/tokens";

type ModuleGroup = (typeof MODULE_GROUPS)[number];

export function isMobileNavActive(pathname: string | null, slug: string): boolean {
  return slug === "" ? pathname === "/" : pathname?.startsWith("/" + slug) ?? false;
}

function focusableIn(drawer: HTMLElement): HTMLElement[] {
  return Array.from(
    drawer.querySelectorAll<HTMLElement>(
      "a[href], button:not([disabled]), input:not([disabled]), " +
        "select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
    ),
  );
}

function handleDrawerKey(event: KeyboardEvent, drawerRef: RefObject<HTMLElement | null>, close: () => void): void {
  if (event.key === "Escape") return closeDrawer(event, close);
  trapDrawerFocus(event, drawerRef);
}

function closeDrawer(event: KeyboardEvent, close: () => void): void {
  event.preventDefault();
  close();
}

function trapDrawerFocus(event: KeyboardEvent, drawerRef: RefObject<HTMLElement | null>): void {
  const drawer = getFocusableDrawer(event, drawerRef);
  if (!drawer) return;
  const focusable = focusableIn(drawer);
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!isFocusBoundary(event, first, last)) return;
  focusDrawerBoundary(event, first, last);
}

function getFocusableDrawer(event: KeyboardEvent, drawerRef: RefObject<HTMLElement | null>): HTMLElement | null {
  if (event.key !== "Tab") return null;
  return drawerRef.current;
}

function focusDrawerBoundary(event: KeyboardEvent, first: HTMLElement, last: HTMLElement): void {
  event.preventDefault();
  if (event.shiftKey) last.focus();
  else first.focus();
}

function isFocusBoundary(event: KeyboardEvent, first: HTMLElement, last: HTMLElement): boolean {
  return event.shiftKey ? document.activeElement === first : document.activeElement === last;
}

export function useMobileDrawerLifecycle(
  open: boolean,
  drawerRef: RefObject<HTMLElement | null>,
  triggerRef: RefObject<HTMLButtonElement | null>,
  closeRef: RefObject<HTMLButtonElement | null>,
  close: () => void,
): void {
  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const trigger = triggerRef.current;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKey = (event: KeyboardEvent) => handleDrawerKey(event, drawerRef, close);
    document.addEventListener("keydown", onKey);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, [close, closeRef, drawerRef, open, triggerRef]);
}

function MobileNavItem({ pathname, slug, label, icon }: {
  pathname: string | null;
  slug: string;
  label: string;
  icon: ModuleGroup["items"][number]["icon"];
}) {
  const active = isMobileNavActive(pathname, slug);
  const Icon = icon;
  return (
    <Link
      href={"/" + slug}
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
      <span className="flex-1 min-w-0 truncate">{label}</span>
    </Link>
  );
}

function MobileNavGroup({
  group,
  pathname,
  activeSlug,
  activeGroup,
  openGroups,
  toggleGroup,
}: {
  group: ModuleGroup;
  pathname: string | null;
  activeSlug: string | undefined;
  activeGroup: string | null;
  openGroups: Set<string>;
  toggleGroup: (group: string) => void;
}) {
  const { expanded, hasActive } = getGroupState(group, openGroups, activeSlug, activeGroup);
  return (
    <div>
      <MobileNavGroupHeader group={group.group} label={GROUP_LABELS[group.group]} expanded={expanded} hasActive={hasActive} toggleGroup={toggleGroup} />
      <MobileNavGroupContent group={group} pathname={pathname} expanded={expanded} />
    </div>
  );
}

function MobileNavGroupHeader({
  group,
  label,
  expanded,
  hasActive,
  toggleGroup,
}: {
  group: string;
  label: string;
  expanded: boolean;
  hasActive: boolean;
  toggleGroup: (group: string) => void;
}) {
  return (
    <button
      type="button"
      data-ui-control
      onClick={() => toggleGroup(group)}
      aria-expanded={expanded}
      className="mt-3 flex w-full items-center justify-between gap-2 rounded-[var(--radius)] px-3 py-1.5 font-display italic text-[13px] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
    >
      <span className="flex items-center gap-1.5">
        {label}
        {!expanded && hasActive && <span className="h-1.5 w-1.5 rounded-full bg-[var(--ring)]" aria-hidden="true" />}
      </span>
      <ChevronRight
        className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-150", expanded && "rotate-90")}
        aria-hidden="true"
      />
    </button>
  );
}

function MobileNavGroupContent({
  group,
  pathname,
  expanded,
}: {
  group: ModuleGroup;
  pathname: string | null;
  expanded: boolean;
}) {
  return (
    <AnimatePresence initial={false}>
      {expanded && (
        <motion.nav
          key="nav"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: EASE_OUT }}
          className="mt-0.5 flex flex-col gap-0.5 overflow-hidden"
          aria-label={GROUP_LABELS[group.group]}
        >
          {group.items.map((module) => (
            <MobileNavItem key={module.slug} pathname={pathname} {...module} />
          ))}
        </motion.nav>
      )}
    </AnimatePresence>
  );
}

function getGroupState(
  group: ModuleGroup,
  openGroups: Set<string>,
  activeSlug: string | undefined,
  activeGroup: string | null,
): { expanded: boolean; hasActive: boolean } {
  return {
    expanded: openGroups.has(group.group) || group.group === activeGroup,
    hasActive: group.items.some((module) => module.slug === activeSlug),
  };
}

export function MobileNavDrawer({
  pathname,
  activeSlug,
  activeGroup,
  openGroups,
  toggleGroup,
  close,
  drawerRef,
  closeRef,
}: {
  pathname: string | null;
  activeSlug: string | undefined;
  activeGroup: string | null;
  openGroups: Set<string>;
  toggleGroup: (group: string) => void;
  close: () => void;
  drawerRef: RefObject<HTMLElement | null>;
  closeRef: RefObject<HTMLButtonElement | null>;
}) {
  return (
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
        onClick={close}
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
            onClick={close}
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
            aria-current={isMobileNavActive(pathname, "") ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
              isMobileNavActive(pathname, "")
                ? "nav-active font-medium"
                : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
            )}
          >
            <Home className="h-4 w-4 shrink-0" aria-hidden="true" />
            Accueil
          </Link>
        </nav>
        {MODULE_GROUPS.map((group) => (
          <MobileNavGroup
            key={group.group}
            group={group}
            pathname={pathname}
            activeSlug={activeSlug}
            activeGroup={activeGroup}
            openGroups={openGroups}
            toggleGroup={toggleGroup}
          />
        ))}
        <div className="mt-auto flex items-center gap-2 border-t border-[var(--glass-border)] px-2 pt-4">
          <NotificationsWidget />
          <DensityToggle />
          <ThemeToggle />
        </div>
      </motion.aside>
    </motion.div>
  );
}
