import { SkeletonHeader, SkeletonCardGrid, Skeleton } from "@/components/ui/skeleton";

/**
 * Cuisine : ModuleHeader (4 onglets), puis l'onglet "Recettes" (par défaut)
 * — barre recherche/filtres puis grille de fiches en 2 colonnes
 * (sm:grid-cols-2, pas 3 : ajusté vs le gabarit de départ).
 */
export default function Loading() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
        <Skeleton className="h-9 w-80 max-w-full rounded-[var(--radius-full)]" /> {/* rail 4 onglets */}
      </div>

      <div className="p-6 space-y-4 animate-fade-in-up">
        <Skeleton className="h-10 w-full max-w-md rounded-lg" /> {/* recherche / filtre ingrédient */}
        <SkeletonCardGrid count={4} cols={2} /> {/* fiches recettes */}
      </div>
    </div>
  );
}
