"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { financeApi, type RebalancingDiff, type RebalancingLine } from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";

const ALL = "Tous";

function fmt(n: number, dec = 2) {
  return n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function ActionBadge({ a }: { a: string }) {
  const map: Record<string, "success" | "destructive" | "outline"> = {
    ACHETER: "success", VENDRE: "destructive", CONSERVER: "outline",
  };
  return <Badge variant={map[a] ?? "outline"}>{a}</Badge>;
}

/** Cellule "cible" : actions entières (hors Trading212) ou % (pie Trading212). */
function CibleCell({ l }: { l: RebalancingLine }) {
  return (
    <div className="leading-tight">
      {l.cible_type === "shares" ? (
        <span className="font-semibold">{l.cible_shares ?? 0} act.</span>
      ) : (
        <span className="font-semibold">pie</span>
      )}
      <div className="text-xs text-[var(--muted-foreground)]">{fmt(l.valeur_cible_eur)} €</div>
    </div>
  );
}

/** Cellule "delta" : actions à acheter/vendre (entiers) + montant €. */
function DeltaCell({ l }: { l: RebalancingLine }) {
  const cls = l.delta_eur > 0 ? "text-[var(--success)]" : l.delta_eur < 0 ? "text-[var(--destructive)]" : "";
  return (
    <div className={`leading-tight text-right ${cls}`}>
      {l.delta_shares != null && l.delta_shares !== 0 && (
        <div className="font-semibold">{l.delta_shares > 0 ? "+" : ""}{l.delta_shares} act.</div>
      )}
      <div className="text-xs">{l.delta_eur > 0 ? "+" : ""}{fmt(l.delta_eur)} €</div>
    </div>
  );
}

export function RebalancingTab() {
  const [diff, setDiff] = useState<RebalancingDiff | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [broker, setBroker] = useState<string>(ALL);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setDiff(await financeApi.rebalancing()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur réseau"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Liste des brokers présents dans le diff
  const brokers = useMemo(
    () => Array.from(new Set((diff?.lignes ?? []).map(l => l.broker))).sort(),
    [diff],
  );

  // Lignes filtrées + sommes internes au broker sélectionné
  const { lignes, sumCible, sumActuel, isPie, single } = useMemo(() => {
    const all = diff?.lignes ?? [];
    const single = broker !== ALL;
    const lignes = single ? all.filter(l => l.broker === broker) : all;
    const sumCible = lignes.reduce((s, l) => s + l.valeur_cible_eur, 0);
    const sumActuel = lignes.reduce((s, l) => s + l.valeur_actuelle_eur, 0);
    const isPie = single && lignes.length > 0 && lignes.every(l => l.cible_type === "pie");
    return { lignes, sumCible, sumActuel, isPie, single };
  }, [diff, broker]);

  if (loading) return <Spinner label="Calcul rebalancing..." />;
  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;
  if (!diff) return (
    <EmptyState
      title="Aucune analyse Buffett disponible"
      description="Lancez une analyse Buffett puis créez le portefeuille optimal pour obtenir les cibles de rebalancing."
    />
  );

  const pctActuel = (v: number) => (sumActuel > 0 ? (v / sumActuel) * 100 : 0);
  const pctCible = (v: number) => (sumCible > 0 ? (v / sumCible) * 100 : 0);

  return (
    <div className="space-y-4">
      {/* Disclaimer */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--warning-muted)] bg-[var(--warning-muted)]
        p-3 text-sm text-[var(--warning-foreground)]">
        ⚠ Affichage uniquement — aucune exécution de trades. Hors Trading212, les cibles sont en
        <strong> actions entières</strong>.
      </div>

      {/* Sélecteur de broker — rebalancer un broker à la fois */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--muted-foreground)] mr-1">Broker :</span>
        {[ALL, ...brokers].map(b => (
          <button key={b} onClick={() => setBroker(b)}
            className={`px-3 py-1.5 text-sm rounded-[var(--radius)] border transition-colors ${
              broker === b
                ? "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "border-[var(--border)] hover:bg-[var(--muted)]"}`}>
            {b}
          </button>
        ))}
      </div>

      {/* Résumé : global (Tous) ou broker sélectionné */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(single
          ? [
              { label: "Détenu (broker)", value: `${fmt(sumActuel)} €` },
              { label: "Cible (broker)", value: `${fmt(sumCible)} €` },
              { label: "Lignes", value: `${lignes.length}` },
              { label: "À ajuster", value: `${lignes.filter(l => l.action !== "CONSERVER").length}` },
            ]
          : [
              { label: "Valeur actuelle", value: `${fmt(diff.valeur_totale_eur)} €` },
              { label: "Budget à déployer", value: `${fmt(diff.budget_total_eur)} €` },
              { label: "À acheter", value: `${diff.n_acheter} ligne(s)`, color: "text-[var(--success)]" },
              { label: "À vendre", value: `${diff.n_vendre} ligne(s)`, color: "text-[var(--destructive)]" },
            ]
        ).map(k => (
          <div key={k.label} className="rounded-[var(--radius-lg)] border border-[var(--border)] p-3">
            <p className="text-xs text-[var(--muted-foreground)]">{k.label}</p>
            <p className={`text-base font-semibold ${"color" in k ? (k.color as string) : ""}`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Alerte de rééquilibrage : positions trop éloignées de leur cible */}
      {diff.n_alertes > 0 && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--destructive)]/30 bg-[color-mix(in_srgb,var(--destructive)_8%,transparent)] px-4 py-2.5 text-sm text-[var(--destructive)]">
          ⚠ {diff.n_alertes} position{diff.n_alertes > 1 ? "s" : ""} déviée{diff.n_alertes > 1 ? "s" : ""} de plus de {fmt(diff.seuil_alerte_pct, 0)} % de leur cible — rééquilibrage conseillé.
        </div>
      )}

      {/* Astuce pie Trading212 */}
      {isPie && (
        <p className="text-xs text-[var(--muted-foreground)]">
          💡 {broker} fonctionne en <strong>pie</strong> : reporte la colonne <strong>Cible interne %</strong>
          {" "}dans la répartition de ta pie (les % somment à 100 % du broker).
        </p>
      )}

      <p className="text-xs text-[var(--muted-foreground)]">
        Cibles basées sur les budgets brokers · run Buffett du {diff.run_date} (run_id={diff.run_id})
      </p>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
              <th className="pb-1 pr-3">{single ? "Ticker" : "Ticker / Broker"}</th>
              <th className="pb-1 pr-3 text-right">Détenu</th>
              {single && <th className="pb-1 pr-3 text-right">Interne actuel %</th>}
              {single
                ? <th className="pb-1 pr-3 text-right">Cible interne %</th>
                : <th className="pb-1 pr-3 text-right">Cible</th>}
              <th className="pb-1 pr-3 text-right">{single ? "Cible" : "Cible %"}</th>
              <th className="pb-1 pr-3 text-right">Prix</th>
              <th className="pb-1 pr-3 text-right">Δ</th>
              <th className="pb-1">Action</th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((l, i) => (
              <tr key={`${l.ticker}__${l.broker}__${i}`}
                className={`border-b border-[var(--border)] hover:bg-[var(--muted)] ${l.alerte ? "bg-[color-mix(in_srgb,var(--destructive)_6%,transparent)]" : ""}`}>
                <td className="py-1.5 pr-3">
                  <div className="font-mono text-xs font-semibold">
                    {l.alerte && <span title={`Écart ${l.ecart_pct > 0 ? "+" : ""}${fmt(l.ecart_pct, 1)} pts`} className="mr-1 text-[var(--destructive)]">⚠</span>}
                    {l.ticker}
                  </div>
                  {!single && <div className="text-xs text-[var(--muted-foreground)]">{l.broker}</div>}
                </td>
                <td className="py-1.5 pr-3 text-right leading-tight">
                  <div>{fmt(l.quantite_actuelle, l.quantite_actuelle % 1 === 0 ? 0 : 2)} act.</div>
                  <div className="text-xs text-[var(--muted-foreground)]">{fmt(l.valeur_actuelle_eur)} €</div>
                </td>
                {single && (
                  <td className="py-1.5 pr-3 text-right text-xs">{fmt(pctActuel(l.valeur_actuelle_eur))}%</td>
                )}
                {single ? (
                  <td className="py-1.5 pr-3 text-right font-semibold">{fmt(pctCible(l.valeur_cible_eur))}%</td>
                ) : (
                  <td className="py-1.5 pr-3 text-right"><CibleCell l={l} /></td>
                )}
                <td className="py-1.5 pr-3 text-right">
                  {single ? <CibleCell l={l} /> : <span className="text-xs">{fmt(l.allocation_cible_pct)}%</span>}
                </td>
                <td className="py-1.5 pr-3 text-right text-xs">{l.prix_unitaire ? `${fmt(l.prix_unitaire)} €` : "—"}</td>
                <td className="py-1.5 pr-3 text-right"><DeltaCell l={l} /></td>
                <td className="py-1.5"><ActionBadge a={l.action} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
