"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TabsContextValue {
  value: string;
  onChange: (value: string) => void;
  registerTab: (value: string) => void;
  tabs: string[];
  id: string;
}

const TabsContext = React.createContext<TabsContextValue>({
  value: "",
  onChange: () => {},
  registerTab: () => {},
  tabs: [],
  id: "",
});

interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

function Tabs({ value, onValueChange, children, className }: TabsProps) {
  const [tabs, setTabs] = React.useState<string[]>([]);
  const id = React.useId();

  const registerTab = React.useCallback((v: string) => {
    setTabs((prev) => (prev.includes(v) ? prev : [...prev, v]));
  }, []);

  return (
    <TabsContext.Provider value={{ value, onChange: onValueChange, registerTab, tabs, id }}>
      <div className={cn("flex flex-col gap-4", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

function TabsList({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <nav
      className={cn("flex gap-0.5 border-b border-[var(--border)] overflow-x-auto", className)}
      role="tablist"
    >
      {children}
    </nav>
  );
}

interface TabsTriggerProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

function TabsTrigger({ value, children, className }: TabsTriggerProps) {
  const ctx = React.useContext(TabsContext);
  const active = ctx.value === value;

  React.useEffect(() => {
    ctx.registerTab(value);
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const idx = ctx.tabs.indexOf(value);
    if (idx === -1) return;
    let next = -1;
    if (e.key === "ArrowRight") next = (idx + 1) % ctx.tabs.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + ctx.tabs.length) % ctx.tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = ctx.tabs.length - 1;
    if (next !== -1) {
      e.preventDefault();
      ctx.onChange(ctx.tabs[next]);
    }
  };

  return (
    <button
      role="tab"
      id={ctx.id + "-tab-" + value}
      aria-selected={active}
      aria-controls={ctx.id + "-panel-" + value}
      tabIndex={active ? 0 : -1}
      onClick={() => ctx.onChange(value)}
      onKeyDown={handleKeyDown}
      className={cn(
        "shrink-0 px-3 py-2 text-sm -mb-px border-b-2 transition-colors duration-150",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-1",
        active
          ? "border-[var(--ring)] text-[var(--foreground)] font-medium"
          : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-[var(--border)]",
        className,
      )}
    >
      {children}
    </button>
  );
}

interface TabsContentProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

function TabsContent({ value, children, className }: TabsContentProps) {
  const ctx = React.useContext(TabsContext);
  if (ctx.value !== value) return null;
  return (
    <div
      role="tabpanel"
      id={ctx.id + "-panel-" + value}
      aria-labelledby={ctx.id + "-tab-" + value}
      tabIndex={0}
      className={cn("focus-visible:outline-none", className)}
    >
      {children}
    </div>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
