"use client";

type Props = {
  label: string;
  unit?: string;
  current: number;
  target: number;
  isMax?: boolean; // si target = limite max (pas un objectif à atteindre)
};

export function MacroBar({ label, unit = "", current, target, isMax = false }: Props) {
  const safeTarget = Math.max(target, 0.01);
  const pct = (current / safeTarget) * 100;
  const clipped = Math.min(Math.max(pct, 0), 100);

  let barClass = "bg-emerald-500";
  if (isMax) {
    if (pct > 100) barClass = "bg-red-500";
    else if (pct > 80) barClass = "bg-amber-500";
    else barClass = "bg-emerald-500";
  } else {
    if (pct < 50) barClass = "bg-amber-500";
    else if (pct < 95) barClass = "bg-blue-500";
    else if (pct <= 110) barClass = "bg-emerald-500";
    else barClass = "bg-red-500";
  }

  return (
    <div>
      <div className="flex justify-between text-xs mb-0.5">
        <span className="font-medium">{label}</span>
        <span className="text-[var(--muted-foreground)] tabular-nums">
          {current.toFixed(label === "Calories" ? 0 : 1)} / {target.toFixed(label === "Calories" ? 0 : 1)} {unit}
          {" "}<span className="opacity-60">({pct.toFixed(0)}%)</span>
        </span>
      </div>
      <div className="h-2 rounded bg-[var(--muted)] overflow-hidden">
        <div className={`h-full ${barClass} transition-all`} style={{ width: `${clipped}%` }} />
      </div>
    </div>
  );
}
