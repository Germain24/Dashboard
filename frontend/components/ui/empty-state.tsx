import * as React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[var(--radius-lg)]",
        "border border-dashed border-[var(--border)] px-6 py-12 text-center",
        className,
      )}
    >
      {icon && (
        <span className="text-[var(--muted-foreground)] opacity-50">{icon}</span>
      )}
      <p className="text-sm font-medium text-[var(--foreground)]">{title}</p>
      {description && (
        <p className="text-xs text-[var(--muted-foreground)] max-w-xs">{description}</p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
