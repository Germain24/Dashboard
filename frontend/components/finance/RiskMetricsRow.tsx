"use client";

/** Ratios de risque du portefeuille (GET /finance/risk), même traitement visuel
 *  que la ligne « Rendement annualisé (TWR) » de SuiviTab. */

// Type local volontaire : lib/types.ts est généré et actuellement désynchronisé.
type RiskRatios = {
  sharpe?: number | null;
  sortino?: number | null;
  max_drawdown_pct?: number | null;
  volatilite_annualisee_pct?: number | null;
  concentration?: string | null;
  periode_debut?: string | null;
};

const fmt = (v: number) => v.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CONCENTRATION_COLORS: Record<string, string> = {
  élevée: "var(--destructive)",
  modérée: "var(--warning)",
  faible: "var(--success)",
};

export function RiskMetricsRow({ metrics }: { metrics: RiskRatios }) {
  const {
    sharpe,
    sortino,
    max_drawdown_pct: drawdown,
    volatilite_annualisee_pct: volatilite,
    concentration,
    periode_debut: periodeDebut,
  } = metrics;
  if (sharpe == null && sortino == null && drawdown == null) return null;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
      <span className="text-[var(--muted-foreground)]">Risque</span>
      {sharpe != null && (
        <span className="flex items-center gap-1.5">
          <span className="text-[var(--muted-foreground)]">Sharpe</span>
          <span className="font-mono font-semibold tabular-nums">{fmt(sharpe)}</span>
        </span>
      )}
      <span className="flex items-center gap-1.5">
        <span className="text-[var(--muted-foreground)]">Sortino</span>
        {sortino != null ? (
          <span className="font-mono font-semibold tabular-nums">{fmt(sortino)}</span>
        ) : (
          // null = aucun rendement sous le taux sans risque : le ratio est infini,
          // pas nul — afficher 0 se lirait comme « mauvais ».
          <span
            className="font-mono text-[var(--muted-foreground)]"
            title="Aucun rendement baissier sur la période : ratio non défini"
          >
            —
          </span>
        )}
      </span>
      {drawdown != null && (
        <span className="flex items-center gap-1.5">
          <span className="text-[var(--muted-foreground)]">Max drawdown</span>
          <span className="font-mono font-semibold tabular-nums">{fmt(drawdown)} %</span>
        </span>
      )}
      {volatilite != null && (
        <span className="flex items-center gap-1.5">
          <span className="text-[var(--muted-foreground)]">Volatilité</span>
          <span className="font-mono font-semibold tabular-nums">{fmt(volatilite)} %</span>
        </span>
      )}
      {concentration && concentration !== "inconnu" && (
        <span className="flex items-center gap-1.5">
          <span className="text-[var(--muted-foreground)]">Concentration</span>
          <span
            className="font-semibold"
            style={{ color: CONCENTRATION_COLORS[concentration] ?? "var(--foreground)" }}
          >
            {concentration}
          </span>
        </span>
      )}
      {periodeDebut && (
        // Les ratios ne portent que sur la période couverte par des relevés :
        // l'historique reconstruit en amont les rendait ininterprétables.
        <span
          className="text-xs text-[var(--muted-foreground)]"
          title="L'historique antérieur au premier relevé broker est une reconstruction : il n'entre dans aucun ratio."
        >
          · depuis le {new Date(periodeDebut).toLocaleDateString("fr-FR")}
        </span>
      )}
    </div>
  );
}
