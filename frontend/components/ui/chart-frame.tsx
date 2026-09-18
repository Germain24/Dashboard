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

function ChartHeading({
  title,
  description,
  action,
}: Pick<ChartFrameProps, "title" | "description" | "action">) {
  if (!title && !action) return null;
  return (
    <div className="mb-3 flex items-start justify-between gap-2">
      <HeadingCopy title={title} description={description} />
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

function HeadingCopy({ title, description }: Pick<ChartFrameProps, "title" | "description">) {
  return (
    <div>
      {title && <p className="text-sm font-medium text-[var(--foreground)]">{title}</p>}
      {description && <p className="text-xs text-[var(--muted-foreground)]">{description}</p>}
    </div>
  );
}

function LegendItem({ item, onToggle }: { item: ChartLegendItem; onToggle?: (label: string) => void }) {
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
    <li>
      {onToggle ? (
        <button
          type="button"
          onClick={() => onToggle(item.label)}
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
}

function ChartLegend({ legend, onLegendToggle }: Pick<ChartFrameProps, "legend" | "onLegendToggle">) {
  if (!legend || legend.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
      {legend.map((item) => (
        <LegendItem key={item.label} item={item} onToggle={onLegendToggle} />
      ))}
    </ul>
  );
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
        "glass-card rounded-[var(--radius-lg)] p-5",
        className,
      )}
    >
      <ChartHeading title={title} description={description} action={action} />
      <div
        className="w-full overflow-hidden"
        style={{ height }}
        role="img"
        aria-label={title ?? "Graphique"}
      >
        {children}
      </div>

      <ChartLegend legend={legend} onLegendToggle={onLegendToggle} />
    </div>
  );
}
