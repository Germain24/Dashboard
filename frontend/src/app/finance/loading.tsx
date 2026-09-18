import { SkeletonHeader, SkeletonStatRow, Skeleton } from "@/components/ui/skeleton";

/**
 * Finance : ModuleHeader (verre collant, 7 onglets) + ObjectifWidget pleine
 * largeur, puis l'onglet "Suivi" (par défaut) — 4 stat-cards + le graphique
 * d'évolution du portefeuille. Le wrapper calque exactement la géométrie de
 * ModuleHeader (px-6 py-4 sticky) pour éviter un saut au montage réel.
 */
export default function Loading() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
        <Skeleton className="h-9 w-[36rem] max-w-full rounded-[var(--radius-full)]" /> {/* rail 7 onglets */}
      </div>

      <div className="px-6 pt-6">
        <Skeleton className="h-16 w-full rounded-lg" /> {/* ObjectifWidget */}
      </div>

      <div className="p-6 space-y-4 animate-fade-in-up">
        <SkeletonStatRow count={4} />
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
          <Skeleton className="h-[260px] w-full rounded-lg" /> {/* graphique portefeuille */}
        </div>
      </div>
    </div>
  );
}
