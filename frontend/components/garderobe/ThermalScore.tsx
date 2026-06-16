export function ThermalScore({
  total,
  target,
  useBody,
  styleScore,
}: {
  total: number;
  target: number;
  useBody: boolean;
  styleScore: number;
}) {
  const gap = target - total;
  const absGap = Math.abs(gap);
  const colorVar =
    absGap < 3 ? "var(--success)" : absGap < 6 ? "var(--warning)" : "var(--destructive)";

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 flex items-center gap-6">
      <div className="text-center">
        <div className="text-[10px] text-[var(--muted-foreground)]">
          Score thermique
        </div>
        <div className="text-xl font-bold" style={{ color: colorVar }}>
          {total.toFixed(1)} / {target.toFixed(1)}
        </div>
        <div className="text-[10px] text-[var(--muted-foreground)]">tenue / cible</div>
      </div>
      <div className="text-sm text-[var(--muted-foreground)]">
        Gap = <span style={{ color: colorVar }}>{gap >= 0 ? "+" : ""}{gap.toFixed(1)}</span>
        {useBody ? " · Body actif" : ""}
      </div>
      <div className="ml-auto text-center">
        <div className="text-[10px] text-[var(--muted-foreground)]">
          Style
        </div>
        <div className="text-xl font-bold">{styleScore.toFixed(0)}%</div>
      </div>
    </div>
  );
}
