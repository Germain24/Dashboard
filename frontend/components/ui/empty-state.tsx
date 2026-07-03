import * as React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * État vide éditorial : la typographie de l'almanach (serif italique) et un
 * fin ornement laiton — pas d'illustration. Un état vide premium est ce qui
 * distingue une app finie.
 */
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
        "flex flex-col items-center justify-center gap-4 rounded-[var(--radius-lg)]",
        "border border-dashed border-[var(--border)] bg-[var(--field)] px-6 py-16 text-center",
        className,
      )}
    >
      {icon && (
        <span className="text-[var(--muted-foreground)] opacity-40">{icon}</span>
      )}
      <p className="font-display italic text-lg text-[var(--foreground)] [text-wrap:balance]">
        {title}
      </p>
      <span
        data-testid="empty-ornament"
        aria-hidden
        className="h-px w-10 bg-[var(--warning)] opacity-60"
      />
      {description && (
        <p className="text-[15px] leading-relaxed text-[var(--muted-foreground)] max-w-xs">
          {description}
        </p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
