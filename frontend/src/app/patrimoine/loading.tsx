import { SkeletonHeader, SkeletonStatRow, SkeletonCardGrid, Skeleton } from "@/components/ui/skeleton";

/**
 * Patrimoine : ModuleHeader sans onglets, puis PatrimoineTab — 3 stat-cards,
 * deux graphiques pleine largeur (répartition par compte, courbe nette
 * investissement) et enfin actifs/passifs sur 2 colonnes.
 */
export default function Loading() {
  return (
    <div className="animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <SkeletonHeader />
      </div>

      <div className="p-6 space-y-6 animate-fade-in-up">
        <SkeletonStatRow count={3} />
        <Skeleton className="h-56 w-full rounded-[var(--radius-lg)]" /> {/* répartition par compte */}
        <Skeleton className="h-32 w-full rounded-[var(--radius-lg)]" /> {/* courbe patrimoine net */}
        <SkeletonCardGrid count={2} cols={2} /> {/* actifs / passifs */}
      </div>
    </div>
  );
}
