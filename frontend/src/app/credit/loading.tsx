import { SkeletonHeader, SkeletonStatRow, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
      </div>

      <div className="p-6 space-y-6 animate-fade-in-up">
        <SkeletonStatRow count={2} />
        <Skeleton className="h-24 w-full rounded-[var(--radius-lg)]" /> {/* projection */}
        <Skeleton className="h-40 w-full rounded-[var(--radius-lg)]" /> {/* comptes */}
        <Skeleton className="h-40 w-full rounded-[var(--radius-lg)]" /> {/* feuille de route */}
      </div>
    </div>
  );
}
