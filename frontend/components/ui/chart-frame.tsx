import * as React from "react";
import { cn } from "@/lib/utils";

export interface ChartLegendItem {
  label: string;
  color: string;
  /** Série masquée (rendu atténué + barré). */
  hidden?: boolean;
}

interface ChartFrameProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  /** Fixed height for the chart area (default 240) */
  height?: number;
  action?: React.ReactNode;
  /** Légende cliquable cohérente (toggle de séries). */
  legend?: ChartLegendItem[];
  /** Appelé au clic sur une entrée de légende (à l'app de masquer la série). */
  onLegendToggle?: (label: string) => void;
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
  legend,
  onLegendToggle,
}: ChartFrameProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5",
        "backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.4]",
        "shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)]",
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

      {legend && legend.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
          {legend.map((item) => {
            const interactive = Boolean(onLegendToggle);
            const content = (
              <>
                <span
                  className="inline-block h-2.5 w-2.5 rounded-[2px] shrink-0"
                  style={{ backgroundColor: item.color, opacity: item.hidden ? 0.3 : 1 }}
                  aria-hidden="true"
                />
                <span
                  className={cn(
                    "text-xs",
                    item.hidden
                      ? "text-[var(--muted-foreground)] line-through"
                      : "text-[var(--foreground)]",
                  )}
                >
                  {item.label}
                </span>
              </>
            );
            return (
              <li key={item.label}>
                {interactive ? (
                  <button
                    type="button"
                    onClick={() => onLegendToggle?.(item.label)}
                    aria-pressed={!item.hidden}
                    className="flex items-center gap-1.5 cursor-pointer hover:opacity-80"
                  >
                    {content}
                  </button>
                ) : (
                  <span className="flex items-center gap-1.5">{content}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
