import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Module } from "@/lib/modules";

export function ModuleCard({ module: m }: { module: Module }) {
  const Icon = m.icon;
  return (
    <Link
      href={"/" + m.slug}
      aria-label={m.label + " - " + m.description}
      className={cn(
        "group relative flex flex-col gap-2.5 rounded-[var(--radius-lg)] border p-4",
        "transition-all duration-150",
        "hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2",
        m.ready
          ? "border-[var(--border)] bg-[var(--card)] hover:border-[var(--ring)]/30"
          : "border-dashed border-[var(--border)] bg-[var(--background-subtle)] opacity-60 hover:opacity-80",
      )}
    >
      {m.ready && (
        <span
          aria-hidden="true"
          className="absolute top-3 right-3 h-1.5 w-1.5 rounded-full bg-[var(--success)] opacity-70"
        />
      )}

      <div
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-[var(--radius)] transition-colors duration-150",
          m.ready
            ? "bg-[var(--muted)] group-hover:bg-[var(--ring)]/10"
            : "bg-[var(--muted)]",
        )}
      >
        <Icon
          className={cn(
            "h-4 w-4 transition-colors duration-150",
            m.ready
              ? "text-[var(--muted-foreground)] group-hover:text-[var(--ring)]"
              : "text-[var(--muted-foreground)]",
          )}
          aria-hidden="true"
        />
      </div>

      <div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold leading-tight">{m.label}</span>
          <ArrowRight
            aria-hidden="true"
            className={cn(
              "h-3.5 w-3.5 text-[var(--muted-foreground)] transition-all duration-150",
              "opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0",
            )}
          />
        </div>
        <p className="mt-0.5 text-xs text-[var(--muted-foreground)] leading-snug line-clamp-2">
          {m.description}
        </p>
      </div>
    </Link>
  );
}
