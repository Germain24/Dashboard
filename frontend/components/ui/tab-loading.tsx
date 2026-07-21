export function TabLoading() {
  return (
    <div role="status" aria-label="Chargement de la section" className="space-y-3">
      <div className="skeleton-shimmer h-9 w-48 rounded-[var(--radius)]" />
      <div className="skeleton-shimmer h-32 w-full rounded-[var(--radius)]" />
      <span className="sr-only">Chargement…</span>
    </div>
  );
}
