import { SkeletonHeader, SkeletonList, Skeleton } from "@/components/ui/skeleton";

/**
 * Agenda : ModuleHeader (4 onglets), puis l'onglet "Aujourd'hui" (par
 * défaut). rows=3 aligné sur le fallback interne d'Agenda.tsx pendant le
 * chargement de la query du jour (même hauteur de lignes, même compte) pour
 * éviter un second saut skeleton → skeleton → contenu.
 */
export default function Loading() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
        <Skeleton className="h-9 w-72 max-w-full rounded-[var(--radius-full)]" /> {/* rail 4 onglets */}
      </div>

      <div className="p-6 animate-fade-in-up">
        <SkeletonList rows={3} />
      </div>
    </div>
  );
}
