import { SkeletonHeader, SkeletonCardGrid, Skeleton } from "@/components/ui/skeleton";

/**
 * Garde-robe : ModuleHeader (7 onglets, dont "Tenue du Jour"), puis l'onglet
 * "Inventaire" (par défaut) — 5 filtres puis une grille de vignettes en 4
 * colonnes (lg:grid-cols-4).
 *
 * Note : Garderobe.tsx remplace tout son rendu (sans header) par un
 * fallback plat tant que ses queries chargent — ce loading.tsx couvre
 * surtout le cas cache-chaud où le contenu réel arrive directement.
 */
export default function Loading() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
        <Skeleton className="h-9 w-[34rem] max-w-full rounded-[var(--radius-full)]" /> {/* rail 7 onglets */}
      </div>

      <div className="p-6 space-y-4 animate-fade-in-up">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
        <SkeletonCardGrid count={8} cols={4} /> {/* vignettes de pièces */}
      </div>
    </div>
  );
}
