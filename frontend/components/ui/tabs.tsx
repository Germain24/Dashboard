"use client";

import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { springs } from "@/lib/motion/tokens";

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
    <div
      className={cn(
        // Contrôle segmenté en verre : rail encastré (.glass-inset),
        // l'actif est une pastille soulevée.
        "flex w-fit max-w-full gap-1 overflow-x-auto rounded-[var(--radius-full)]",
        "glass-inset border border-[var(--glass-border)] p-1",
        className,
      )}
      role="tablist"
    >
      {children}
    </div>
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
      const nextValue = ctx.tabs[next];
      ctx.onChange(nextValue);
      document.getElementById(ctx.id + "-tab-" + nextValue)?.focus();
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
        "relative shrink-0 rounded-[var(--radius-full)] px-3.5 py-1.5 text-sm",
        "transition-[color] duration-200 ease-[var(--ease-out)]",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-1 focus-visible:rounded-[var(--radius-full)]",
        active
          ? "text-[var(--foreground)] font-medium"
          : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
        className,
      )}
    >
      {active && (
        <motion.span
          layoutId={ctx.id + "-pill"}
          transition={springs.soft}
          data-testid="tab-pill"
          aria-hidden
          className="absolute inset-0 rounded-[var(--radius-full)] bg-[var(--glass-strong)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-sm)]"
        />
      )}
      <span className="relative z-10">{children}</span>
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
    <motion.div
      role="tabpanel"
      id={ctx.id + "-panel-" + value}
      aria-labelledby={ctx.id + "-tab-" + value}
      tabIndex={0}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springs.soft}
      className={cn("focus-visible:outline-none", className)}
    >
      {children}
    </motion.div>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
