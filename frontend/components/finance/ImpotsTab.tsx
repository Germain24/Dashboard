"use client";

/** Impôts — plus-values de cession sur CTO (PEA exclu, régime différent).
 *  Calcule automatiquement le gain réalisé (FIFO depuis les transactions
 *  importées) et compare PFU (Flat Tax 30%) vs option barème progressif. */

import { useState } from "react";
import { useCalculImpots, useVentesImpots } from "@/lib/queries/finance";
import { Dialog, DialogHeader, DialogTitle, DialogBody } from "@/components/ui/dialog";

const eur = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(n);

export function ImpotsTab() {
  const anneeActuelle = new Date().getFullYear();
  const [annee, setAnnee] = useState(anneeActuelle - 1);
  const [autresRevenus, setAutresRevenus] = useState(0);
  const [parts, setParts] = useState(1);
  const [moinsValuesAnterieures, setMoinsValuesAnterieures] = useState(0);
  const [detailOuvert, setDetailOuvert] = useState(false);

  const { data, isLoading, isError } = useCalculImpots({
    annee, autres_revenus: autresRevenus, parts, moins_values_anterieures: moinsValuesAnterieures,
  });
  const { data: ventes } = useVentesImpots({ annee }, detailOuvert);

  return (
    <div className="space-y-6">
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4 text-sm text-[var(--muted-foreground)]">
        Plus-value de cession sur compte-titres ordinaire (CTO) — le PEA a son propre régime, non couvert ici.
        Le gain net est calculé en FIFO depuis les transactions importées (Trading212…). Choisis l'option qui
        s'applique à <strong>tous</strong> tes revenus du capital de l'année (pas de mix ligne par ligne).
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="text-sm">
          Année
          <input type="number" value={annee} onChange={(e) => setAnnee(Number(e.target.value))}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Autres revenus imposables (€)
          <input type="number" value={autresRevenus} onChange={(e) => setAutresRevenus(Number(e.target.value))}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Parts (quotient familial)
          <input type="number" step="0.5" value={parts} onChange={(e) => setParts(Number(e.target.value))}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Moins-values antérieures au grand livre (€)
          <input type="number" value={moinsValuesAnterieures}
                 onChange={(e) => setMoinsValuesAnterieures(Number(e.target.value))}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">Calcul…</p>}
      {isError && <p className="text-sm text-[var(--destructive)]">Erreur de calcul.</p>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Stat label={`Gain brut ${annee}`} value={eur(data.gain_brut)} onClick={() => setDetailOuvert(true)} />
            <Stat label="Gain net imposable" value={eur(data.gain_net_imposable)} strong />
            <Stat label="Report de moins-values restant" value={eur(data.report_moins_values_restant)}
                  negative={data.report_moins_values_restant > 0} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <RegimeCard
              title="PFU (Flat Tax 30%)" regime={data.pfu}
              recommande={data.recommande === "pfu"}
            />
            <RegimeCard
              title="Barème progressif (sur option)" regime={data.bareme}
              recommande={data.recommande === "bareme"}
            />
          </div>

          {Object.keys(data.historique_par_annee).length > 1 && (
            <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
              <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Historique par année</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--muted-foreground)]">
                    <th className="pb-1">Année</th>
                    <th className="pb-1 text-right">Gain brut</th>
                    <th className="pb-1 text-right">Gain net imposable</th>
                    <th className="pb-1 text-right">Report après</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.historique_par_annee).map(([y, row]) => (
                    <tr key={y} className="border-t border-[var(--glass-border)]">
                      <td className="py-1">{y}</td>
                      <td className="py-1 text-right tabular-nums">{eur(row.gain_brut)}</td>
                      <td className="py-1 text-right tabular-nums">{eur(row.gain_net_imposable)}</td>
                      <td className="py-1 text-right tabular-nums">{eur(row.report_apres)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <Dialog open={detailOuvert} onClose={() => setDetailOuvert(false)} className="max-w-3xl">
        <DialogHeader onClose={() => setDetailOuvert(false)}>
          <DialogTitle>Ventes détaillées {annee}</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {!ventes && <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>}
          {ventes && ventes.ventes.length === 0 && (
            <p className="text-sm text-[var(--muted-foreground)]">Aucune vente en {annee}.</p>
          )}
          {ventes && ventes.ventes.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--muted-foreground)]">
                    <th className="pb-1 pr-3">Date</th>
                    <th className="pb-1 pr-3">Titre</th>
                    <th className="pb-1 pr-3 text-right">Qté</th>
                    <th className="pb-1 pr-3 text-right">Prix achat moyen</th>
                    <th className="pb-1 pr-3 text-right">Prix vente</th>
                    <th className="pb-1 pr-3 text-right">Plus-value</th>
                    <th className="pb-1 text-right">Impôt PFU estimé</th>
                  </tr>
                </thead>
                <tbody>
                  {ventes.ventes.map((v, i) => (
                    <tr key={i} className="border-t border-[var(--glass-border)]">
                      <td className="py-1 pr-3 whitespace-nowrap">{v.date.slice(0, 10)}</td>
                      <td className="py-1 pr-3 font-mono text-xs">{v.ticker}</td>
                      <td className="py-1 pr-3 text-right tabular-nums">{v.quantite}</td>
                      <td className="py-1 pr-3 text-right tabular-nums">{eur(v.prix_achat_moyen)}</td>
                      <td className="py-1 pr-3 text-right tabular-nums">{eur(v.prix_vente)}</td>
                      <td className={`py-1 pr-3 text-right tabular-nums ${v.plus_value >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
                        {eur(v.plus_value)}
                      </td>
                      <td className="py-1 text-right tabular-nums">{eur(v.impot_estime_pfu)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-[var(--muted-foreground)]">
            Impôt PFU estimé au taux plein (30 %) par ligne, à titre indicatif -- l&apos;imputation réelle des
            moins-values antérieures se fait au niveau annuel (cf. ci-dessus), pas ligne par ligne.
          </p>
        </DialogBody>
      </Dialog>
    </div>
  );
}

function Stat({ label, value, strong, negative, onClick }: {
  label: string; value: string; strong?: boolean; negative?: boolean; onClick?: () => void;
}) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp
      onClick={onClick}
      className={`rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3 text-left ${onClick ? "cursor-pointer hover:bg-[var(--muted)] transition-colors" : ""}`}
    >
      <div className="text-xs text-[var(--muted-foreground)]">{label}{onClick ? " (détail →)" : ""}</div>
      <div className={`tabular-nums ${strong ? "text-xl font-semibold" : "text-base"} ${negative ? "text-[var(--warning-foreground)]" : "text-[var(--foreground)]"}`}>
        {value}
      </div>
    </Comp>
  );
}

function RegimeCard({ title, regime, recommande }: {
  title: string; regime: { ir: number; social: number; total: number }; recommande: boolean;
}) {
  return (
    <div className={`rounded-[var(--radius-lg)] border p-4 ${recommande ? "border-[var(--success)] bg-[var(--success)]/5" : "border-[var(--glass-border)] bg-[var(--card)]"}`}>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-semibold">{title}</p>
        {recommande && <span className="rounded bg-[var(--success)] px-1.5 py-0.5 text-[10px] font-medium text-white">Recommandé</span>}
      </div>
      <dl className="space-y-1 text-sm">
        <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">Impôt sur le revenu</dt><dd className="tabular-nums">{eur(regime.ir)}</dd></div>
        <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">Prélèvements sociaux</dt><dd className="tabular-nums">{eur(regime.social)}</dd></div>
        <div className="mt-1 flex justify-between border-t border-[var(--glass-border)] pt-1 font-semibold"><dt>Total</dt><dd className="tabular-nums">{eur(regime.total)}</dd></div>
      </dl>
    </div>
  );
}
