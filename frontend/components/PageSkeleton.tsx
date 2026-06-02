/**
 * Skeleton de chargement unifié pour les pages module.
 * Utilisé par les fichiers `loading.tsx` de chaque route (App Router).
 */
export function PageSkeleton() {
  return (
    <div className="p-6 space-y-4 animate-fade-in">
      <div className="h-7 w-48 rounded-md bg-[var(--card)] skeleton-shimmer" />
      <div className="h-4 w-64 rounded-md bg-[var(--card)] skeleton-shimmer" />
      <div className="grid gap-3 sm:grid-cols-3 mt-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-16 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
      ))}
    </div>
  );
}

export default PageSkeleton;
