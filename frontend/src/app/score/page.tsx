"use client";

/** Page Score de forme (type Garmin) : score quotidien agrégé (sommeil + sport
 *  + nutrition), évolution, et liens vers les vues détaillées (Journal de vie,
 *  Vue 360, Bilan mensuel). Fusionne les anciens Vue 360 / Journal de vie. */

import Link from "next/link";
import { Gauge, Moon, Dumbbell, Apple } from "lucide-react";
import { ModuleHeader } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useScore, useScoreHistory } from "@/lib/queries/sante";

const COMPONENTS = [
  { key: "sommeil", label: "Sommeil", Icon: Moon, color: "#6366f1" },
  { key: "sport", label: "Sport", Icon: Dumbbell, color: "#f59e0b" },
  { key: "nutrition", label: "Nutrition", Icon: Apple, color: "#22c55e" },
] as const;

const LINKS = [
  { href: "/snapshot", label: "Journal de vie" },
  { href: "/vue-360", label: "Vue 360 (détails)" },
  { href: "/bilan", label: "Bilan mensuel" },
];

function tone(score: number): { label: string; color: string } {
  if (score >= 80) return { label: "Excellent", color: "var(--success)" };
  if (score >= 60) return { label: "Bon", color: "#22c55e" };
  if (score >= 40) return { label: "Moyen", color: "#f59e0b" };
  return { label: "À surveiller", color: "var(--destructive)" };
}

export default function ScorePage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Score" subtitle="Ta forme du jour : sommeil · sport · nutrition" />
      <div className="p-6">
        <ErrorBoundary label="Score">
          <ScoreContent />
        </ErrorBoundary>
      </div>
    </div>
  );
}

function ScoreContent() {
  const { data, isLoading } = useScore();
  const histQ = useScoreHistory(90);

  if (isLoading || !data) return <Skeleton className="h-40" />;

  const score = data.score;
  const t = score != null ? tone(score) : { label: "Pas encore de données", color: "var(--muted-foreground)" };

  return (
    <div className="space-y-6">
      {/* Score global */}
      <div className="flex flex-wrap items-center gap-6 rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-4"
          style={{ borderColor: t.color }}>
          <div className="text-center">
            <div className="font-display text-3xl tabular-nums" style={{ color: t.color }}>
              {score != null ? Math.round(score) : "—"}
            </div>
            <div className="text-[10px] text-[var(--muted-foreground)]">/ 100</div>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Gauge size={16} style={{ color: t.color }} aria-hidden="true" />
            <span className="text-lg font-semibold" style={{ color: t.color }}>{t.label}</span>
          </div>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Moyenne des composantes disponibles. Renseigne sommeil, entraînements et nutrition
            pour un score complet.
          </p>
        </div>
      </div>

      {/* Composantes */}
      <div className="grid gap-3 sm:grid-cols-3">
        {COMPONENTS.map(({ key, label, Icon, color }) => {
          const v = data.composantes[key];
          return (
            <div key={key} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="mb-2 flex items-center gap-2">
                <Icon size={15} style={{ color }} aria-hidden="true" />
                <span className="text-sm font-medium">{label}</span>
                <span className="ml-auto tabular-nums text-sm font-semibold" style={{ color }}>
                  {v != null ? Math.round(v) : "—"}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
                <div className="h-full rounded-full transition-all"
                  style={{ width: `${v ?? 0}%`, background: color }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Détails bruts */}
      <p className="text-xs text-[var(--muted-foreground)]">
        Sommeil&nbsp;: {data.details.sommeil_h != null ? `${data.details.sommeil_h} h` : "—"} ·
        {" "}Séances (7 j)&nbsp;: {data.details.sessions_7j} ·
        {" "}Nutrition&nbsp;: {data.details.kcal_consommees != null
          ? `${Math.round(data.details.kcal_consommees)} / ${Math.round(data.details.kcal_cible ?? 0)} kcal`
          : "—"}
      </p>

      {/* Évolution */}
      <ScoreCurve points={histQ.data?.points ?? []} />

      {/* Liens vers les vues détaillées (fusion Vue 360 + Journal de vie) */}
      <div className="flex flex-wrap gap-2">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm hover:bg-[var(--muted)]">
            {l.label} →
          </Link>
        ))}
      </div>
    </div>
  );
}

function ScoreCurve({ points }: { points: { date: string; score: number | null }[] }) {
  const pts = points.filter((p) => p.score != null) as { date: string; score: number }[];
  if (pts.length < 2) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Évolution du score</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">La courbe se construit au fil des jours.</p>
      </div>
    );
  }
  const W = 100, H = 30;
  const xs = points.length;
  const idxOf = (p: { date: string }) => points.findIndex((q) => q.date === p.date);
  const coords = pts
    .map((p) => `${((idxOf(p) / (xs - 1)) * W).toFixed(2)},${(H - (p.score / 100) * H).toFixed(2)}`)
    .join(" ");
  const last = pts[pts.length - 1].score;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Évolution du score · 90 j</p>
        <span className="text-xs tabular-nums text-[var(--foreground)]">{Math.round(last)}/100</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full"
        role="img" aria-label="Courbe du score de forme">
        <polyline points={coords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}
