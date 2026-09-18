"use client";

/** Courbe d'équité d'un backtest (base 100).
 *
 *  L'API renvoyait déjà `equity` et `dates`, mais seul le rendement final était
 *  affiché : la série n'était jamais tracée.
 */

import { useId, useMemo, useState } from "react";

export function BacktestChart({
  equity,
  dates,
  label,
}: {
  equity: number[];
  dates?: string[];
  label: string;
}) {
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);

  const model = useMemo(() => {
    const points = equity.filter((value) => Number.isFinite(value));
    if (points.length < 2) return null;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const span = max - min || 1;
    // Marge verticale de 6 % : une courbe collée aux bords se lit mal.
    const low = min - span * 0.06;
    const high = max + span * 0.06;
    const range = high - low || 1;
    const width = 100;
    const height = 32;
    const xFor = (index: number) => (index / (points.length - 1)) * width;
    const yFor = (value: number) => height - ((value - low) / range) * height;
    const line = points
      .map((value, index) => `${index === 0 ? "M" : "L"}${xFor(index).toFixed(3)},${yFor(value).toFixed(3)}`)
      .join(" ");
    // Plus haut sommet atteint avant chaque point → plus forte baisse subie.
    let peak = points[0];
    let worstDrawdown = 0;
    for (const value of points) {
      peak = Math.max(peak, value);
      worstDrawdown = Math.min(worstDrawdown, value / peak - 1);
    }
    return {
      points, min, max, low, range, width, height, line, xFor, yFor,
      worstDrawdown: worstDrawdown * 100,
      first: points[0],
      last: points[points.length - 1],
    };
  }, [equity]);

  if (!model) return null;

  const hovered = hover != null ? model.points[hover] : null;
  const hoveredDate = hover != null ? dates?.[hover] : undefined;
  const positive = model.last >= model.first;
  const stroke = positive ? "var(--success)" : "var(--destructive)";

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">{label}</p>
        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
          {hovered != null
            ? `${hoveredDate ? `${hoveredDate} · ` : ""}${hovered.toFixed(1)}`
            : `plus forte baisse ${model.worstDrawdown.toFixed(1)} %`}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${model.width} ${model.height}`}
        preserveAspectRatio="none"
        className="h-28 w-full"
        role="img"
        aria-label={`${label} : de ${model.first.toFixed(0)} à ${model.last.toFixed(0)}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          if (bounds.width <= 0) return;
          const ratio = (event.clientX - bounds.left) / bounds.width;
          const index = Math.round(ratio * (model.points.length - 1));
          setHover(Math.min(Math.max(index, 0), model.points.length - 1));
        }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.25" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Base 100 : repère du capital de départ. */}
        {model.low < 100 && 100 < model.low + model.range && (
          <line
            x1="0" x2={model.width}
            y1={model.yFor(100)} y2={model.yFor(100)}
            stroke="var(--border)" strokeWidth="0.3" strokeDasharray="1.5 1.5"
            vectorEffect="non-scaling-stroke"
          />
        )}
        <path
          d={`${model.line} L${model.width},${model.height} L0,${model.height} Z`}
          fill={`url(#${gradientId})`}
          stroke="none"
        />
        <path
          d={model.line}
          fill="none"
          stroke={stroke}
          strokeWidth="1.2"
          vectorEffect="non-scaling-stroke"
        />
        {hover != null && (
          <line
            x1={model.xFor(hover)} x2={model.xFor(hover)}
            y1="0" y2={model.height}
            stroke="var(--muted-foreground)" strokeWidth="0.3"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{dates?.[0] ?? "début"}</span>
        <span>
          base {model.first.toFixed(0)} → {model.last.toFixed(0)}
        </span>
        <span>{dates?.[dates.length - 1] ?? "fin"}</span>
      </div>
    </div>
  );
}
