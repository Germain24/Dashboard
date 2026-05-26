import * as React from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-[var(--radius)] bg-[var(--muted)]",
        className,
      )}
      {...props}
    />
  );
}

/** Pre-built skeleton for a module header */
function ModuleSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Chargement">
      <div className="flex items-center gap-3">
        <Skeleton className="h-6 w-6 rounded-full" />
        <Skeleton className="h-6 w-40" />
        <Skeleton className="ml-auto h-5 w-20" />
      </div>
      <div className="flex gap-1 border-b border-[var(--border)] pb-0">
        {[80, 72, 64, 88].map((w, i) => (
          <Skeleton key={i} className={`h-9 w-${w === 80 ? 20 : w === 72 ? 18 : w === 64 ? 16 : 22}`} style={{ width: w }} />
        ))}
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}

export { Skeleton, ModuleSkeleton };
