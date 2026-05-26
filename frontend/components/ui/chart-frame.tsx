import * as React from "react";
import { cn } from "@/lib/utils";

interface ChartFrameProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  /** Fixed height for the chart area (default 240) */
  height?: number;
  action?: React.ReactNode;
}

/**
 * Wrapper standard pour tous les graphes SVG de Mission Control.
 * Gère le titre, la description optionnelle, et un conteneur responsive.
 */
export function ChartFrame({
  title,
  description,
  children,
  className,
  height = 240,
  action,
}: ChartFrameProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--card)] p-4",
        className,
      )}
    >
      {(title || action) && (
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            {title && (
              <p className="text-sm font-medium text-[var(--foreground)]">{title}</p>
            )}
            {description && (
              <p className="text-xs text-[var(--muted-foreground)]">{description}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div
        className="w-full overflow-hidden"
        style={{ height }}
        role="img"
        aria-label={title ?? "Graphique"}
      >
        {children}
      </div>
    </div>
  );
}
