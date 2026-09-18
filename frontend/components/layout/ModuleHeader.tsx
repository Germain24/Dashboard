"use client";

/**
 * En-tête de module unifié (liquid glass).
 *
 * Barre de verre collante : titre en serif éditorial, sous-titre, et un
 * contrôle d'onglets segmenté en verre (pastille soulevée pour l'actif).
 * Remplace les en-têtes `px-6 py-5 border-b` + onglets inline dupliqués page
 * par page. Le corps de l'onglet reste géré par chaque page.
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ElementType,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { FreshnessIndicator } from "@/components/FreshnessIndicator";

export type ModuleTab = {
  id: string;
  label: string;
  icon?: ElementType;
};

interface ModuleHeaderProps {
  title: string;
  subtitle?: string;
  tabs?: ModuleTab[];
  active?: string;
  onChange?: (id: string) => void;
  /**
   * Identifiant du panneau actif. À associer à `ModuleTabPanel` afin que les
   * onglets restent reliés à leur contenu, même quand le module ne monte que
   * l'onglet sélectionné.
   */
  panelId?: string;
  /** Actions optionnelles alignées à droite du titre (boutons, filtres). */
  actions?: React.ReactNode;
}

type ModuleTabPanelProps = {
  panelId: string;
  activeTab: string;
  children: ReactNode;
  className?: string;
};

type TabScrollState = {
  hasOverflow: boolean;
  canScrollBack: boolean;
  canScrollForward: boolean;
};

const INITIAL_TAB_SCROLL_STATE: TabScrollState = {
  hasOverflow: false,
  canScrollBack: false,
  canScrollForward: false,
};

export function moduleTabId(panelId: string, tabId: string) {
  return `${panelId}-tab-${tabId}`;
}

/**
 * Panneau associé à un `ModuleHeader` à onglets.
 *
 * Les modules ne conservent que l'onglet actif monté pour éviter de charger
 * leurs vues lourdes en arrière-plan. Le panneau garde donc un identifiant
 * stable, tandis que son libellé suit l'onglet actif.
 */
export function ModuleTabPanel({ panelId, activeTab, children, className }: ModuleTabPanelProps) {
  return (
    <div
      id={panelId}
      role="tabpanel"
      aria-labelledby={moduleTabId(panelId, activeTab)}
      tabIndex={0}
      className={cn(
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function ModuleHeader({
  title,
  subtitle,
  tabs,
  active,
  onChange,
  panelId,
  actions,
}: ModuleHeaderProps) {
  const tabsId = useId();
  const tabListRef = useRef<HTMLDivElement>(null);
  const [tabScroll, setTabScroll] = useState<TabScrollState>(INITIAL_TAB_SCROLL_STATE);
  const tabScopeId = panelId ?? tabsId;

  const updateTabScroll = useCallback(() => {
    const list = tabListRef.current;
    if (!list) return;
    const hasOverflow = list.scrollWidth > list.clientWidth + 1;
    const next = {
      hasOverflow,
      canScrollBack: hasOverflow && list.scrollLeft > 1,
      canScrollForward: hasOverflow && list.scrollLeft + list.clientWidth < list.scrollWidth - 1,
    };
    setTabScroll((current) =>
      current.hasOverflow === next.hasOverflow &&
      current.canScrollBack === next.canScrollBack &&
      current.canScrollForward === next.canScrollForward
        ? current
        : next,
    );
  }, []);

  useEffect(() => {
    const list = tabListRef.current;
    if (!list) return;

    updateTabScroll();
    list.addEventListener("scroll", updateTabScroll, { passive: true });
    window.addEventListener("resize", updateTabScroll);
    const observer =
      typeof ResizeObserver === "undefined" ? undefined : new ResizeObserver(updateTabScroll);
    observer?.observe(list);

    return () => {
      list.removeEventListener("scroll", updateTabScroll);
      window.removeEventListener("resize", updateTabScroll);
      observer?.disconnect();
    };
  }, [tabs?.length, updateTabScroll]);

  const scrollTabs = (direction: -1 | 1) => {
    const list = tabListRef.current;
    if (!list) return;
    list.scrollBy({ left: direction * Math.max(160, list.clientWidth * 0.8), behavior: "smooth" });
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!tabs?.length) return;
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    event.preventDefault();
    const nextTab = tabs[next];
    onChange?.(nextTab.id);
    window.requestAnimationFrame(() => {
      document.getElementById(moduleTabId(tabScopeId, nextTab.id))?.focus();
    });
  };

  return (
    <div className="glass-panel sticky top-12 z-[var(--z-header)] border-b border-[var(--glass-border)] px-4 py-3 md:top-0 md:px-6 md:py-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3 md:mb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-xl text-[var(--foreground)] sm:text-2xl">{title}</h1>
            <FreshnessIndicator />
          </div>
          {subtitle && <p className="mt-0.5 text-sm text-[var(--muted-foreground)]">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>

      {tabs && tabs.length > 0 && (
        <div className="relative w-fit max-w-full">
          <div
            ref={tabListRef}
            role="tablist"
            aria-label={`Sections de ${title}`}
            aria-describedby={tabScroll.hasOverflow ? `${tabScopeId}-scroll-hint` : undefined}
            className="flex w-fit max-w-full snap-x snap-mandatory gap-1 overflow-x-auto scroll-smooth rounded-[var(--radius-full)] border border-[var(--glass-border)] bg-[var(--field)] p-1 no-scrollbar"
          >
            {tabs.map((tab, index) => {
              const Icon = tab.icon;
              const isActive = active === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={moduleTabId(tabScopeId, tab.id)}
                  aria-controls={panelId}
                  aria-selected={isActive}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => onChange?.(tab.id)}
                  onKeyDown={(event) => handleTabKeyDown(event, index)}
                  className={cn(
                    "springy snap-start flex shrink-0 items-center gap-1.5 rounded-[var(--radius-full)] px-3.5 py-1.5 text-sm font-medium",
                    isActive
                      ? "bg-[var(--glass-strong)] text-[var(--foreground)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-sm)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
                  )}
                >
                  {Icon && <Icon size={15} className="shrink-0" aria-hidden="true" />}
                  {tab.label}
                </button>
              );
            })}
          </div>

          {tabScroll.hasOverflow && (
            <span id={`${tabScopeId}-scroll-hint`} className="sr-only">
              Fais défiler horizontalement pour voir les autres sections.
            </span>
          )}

          {tabScroll.canScrollBack && (
            <button
              type="button"
              onClick={() => scrollTabs(-1)}
              aria-label="Voir les onglets précédents"
              className="absolute inset-y-1 left-1 z-10 grid h-8 w-8 place-items-center rounded-full border border-[var(--glass-border)] bg-[var(--card)]/95 text-[var(--foreground)] shadow-[var(--shadow-sm)] md:hidden"
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
          )}

          {tabScroll.canScrollForward && (
            <button
              type="button"
              onClick={() => scrollTabs(1)}
              aria-label="Voir les onglets suivants"
              className="absolute inset-y-1 right-1 z-10 grid h-8 w-8 place-items-center rounded-full border border-[var(--glass-border)] bg-[var(--card)]/95 text-[var(--foreground)] shadow-[var(--shadow-sm)] md:hidden"
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
