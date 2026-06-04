import type { Module } from "@/lib/modules";

export function ModulePlaceholder({ module: m }: { module: Module }) {
  const Icon = m.icon;
  return (
    <div className="max-w-2xl">
      <div className="mb-6 flex items-center gap-3">
        <Icon className="h-6 w-6 text-[var(--muted-foreground)]" aria-hidden="true" />
        <h1 className="text-2xl font-semibold tracking-tight">{m.label}</h1>
        <span className="ml-auto rounded-full border border-[var(--border)] px-2.5 py-1 text-xs font-medium text-[var(--muted-foreground)]">
          À venir
        </span>
      </div>
      <p className="text-[var(--muted-foreground)]">{m.description}</p>
      <div className="mt-8 rounded-lg border border-dashed border-[var(--border)] bg-[var(--muted)] p-6 text-sm text-[var(--muted-foreground)]">
        Ce module n&apos;est pas encore disponible. Son contenu arrivera dans une
        prochaine version.
      </div>
    </div>
  );
}
