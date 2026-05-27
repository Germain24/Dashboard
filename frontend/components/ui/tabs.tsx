"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/* ── Tabs container ─────────────────────────────────────── */
interface TabsContextValue {
  value: string;
  onChange: (value: string) => void;
}

const TabsContext = React.createContext<TabsContextValue>({
  value: "",
  onChange: () => {},
});

interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onChange: onValueChange }}>
      <div className={cn("flex flex-col gap-4", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

/* ── Tab list (nav bar) ─────────────────────────────────── */
function TabsList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <nav
      className={cn(
        "flex gap-0.5 border-b border-[var(--border)] overflow-x-auto",
        className,
      )}
      role="tablist"
    >
      {children}
    </nav>
  );
}

/* ── Individual tab trigger ─────────────────────────────── */
interface TabsTriggerProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

function TabsTrigger({ value, children, className }: TabsTriggerProps) {
  const ctx = React.useContext(TabsContext);
  const active = ctx.value === value;
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={() => ctx.onChange(value)}
      className={cn(
        "shrink-0 px-3 py-2 text-sm -mb-px border-b-2 transition-colors",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-1",
        active
          ? "border-[var(--ring)] text-[var(--foreground)] font-medium"
          : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
        className,
      )}
    >
      {children}
    </button>
  );
}

/* ── Tab content panel ──────────────────────────────────── */
interface TabsContentProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

function TabsContent({ value, children, className }: TabsContentProps) {
  const ctx = React.useContext(TabsContext);
  if (ctx.value !== value) return null;
  return (
    <div role="tabpanel" className={cn(className)}>
      {children}
    </div>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
