import Link from "next/link";
import type { Module } from "@/lib/modules";

export function ModuleCard({ module: m }: { module: Module }) {
  const Icon = m.icon;
  return (
    <Link
      href={`/${m.slug}`}
      className="group flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--accent)]"
    >
      <div className="flex items-center justify-between">
        <Icon className="h-5 w-5 text-[var(--muted-foreground)]" />
        <span className="rounded-md bg-[var(--muted)] px-2 py-0.5 text-[10px] text-[var(--muted-foreground)]">
          {m.conv}
        </span>
      </div>
      <div className="text-base font-medium">{m.label}</div>
      <p className="text-sm text-[var(--muted-foreground)]">{m.description}</p>
    </Link>
  );
}
