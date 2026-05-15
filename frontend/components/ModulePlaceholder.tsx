import type { Module } from "@/lib/modules";

export function ModulePlaceholder({ module: m }: { module: Module }) {
  const Icon = m.icon;
  return (
    <div className="max-w-2xl">
      <div className="mb-6 flex items-center gap-3">
        <Icon className="h-6 w-6 text-[var(--muted-foreground)]" />
        <h1 className="text-2xl font-semibold tracking-tight">{m.label}</h1>
        <span className="ml-auto rounded-md bg-[var(--muted)] px-2 py-1 text-xs text-[var(--muted-foreground)]">
          {m.conv}
        </span>
      </div>
      <p className="text-[var(--muted-foreground)]">{m.description}</p>
      <div className="mt-8 rounded-lg border border-dashed border-[var(--border)] bg-[var(--muted)] p-6 text-sm text-[var(--muted-foreground)]">
        Module non implémenté en CONV 1. Le contenu réel sera ajouté dans{" "}
        <span className="font-mono">{m.conv}</span>.
      </div>
    </div>
  );
}
