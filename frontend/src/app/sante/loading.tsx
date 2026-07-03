import { SkeletonHeader, SkeletonStatRow, SkeletonList, Skeleton } from "@/components/ui/skeleton";

/**
 * Santé : ModuleHeader (5 onglets), puis l'onglet "Jour" (par défaut) —
 * Water/Sleep sur 2 colonnes, suivis des widgets pleine largeur (alerte
 * énergie, qualité nutrition, dépense entraînement).
 *
 * Note : Sante.tsx remplace tout son rendu (sans header) par un fallback
 * plat tant que ses propres queries chargent — ce loading.tsx couvre
 * surtout le cas cache-chaud où le contenu réel arrive directement.
 */
export default function Loading() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
        <Skeleton className="h-9 w-96 max-w-full rounded-[var(--radius-full)]" /> {/* rail 5 onglets */}
      </div>

      <div className="p-6 space-y-4 animate-fade-in-up">
        <SkeletonStatRow count={2} /> {/* Water / Sleep */}
        <SkeletonList rows={3} /> {/* alertes & widgets pleine largeur */}
      </div>
    </div>
  );
}
