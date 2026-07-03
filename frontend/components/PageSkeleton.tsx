import {
  SkeletonHeader,
  SkeletonStatRow,
  SkeletonCardGrid,
} from "@/components/ui/skeleton";

/**
 * Skeleton générique des pages module : calqué sur le gabarit commun
 * (ModuleHeader + rangée de stats + grille de cartes). Les modules denses
 * ont leur propre loading.tsx sur mesure.
 */
export function PageSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <SkeletonStatRow count={3} />
      <SkeletonCardGrid count={6} cols={3} />
    </div>
  );
}

export default PageSkeleton;
