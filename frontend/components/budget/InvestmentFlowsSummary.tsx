"use client";

import { useBudgetInvestmentFlows } from "@/lib/queries/budget";

function formatMoney(value: number, currency: string) {
  try {
    return new Intl.NumberFormat("fr-CA", {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: 2,
    }).format(value ?? 0);
  } catch {
    return `${new Intl.NumberFormat("fr-CA", { maximumFractionDigits: 2 }).format(value ?? 0)} ${currency}`;
  }
}

function sourceLabel(source: string) {
  if (source === "platform") return "Plateforme";
  if (source === "category") return "Catégorie";
  if (source === "mixed") return "Banque + plateforme";
  return "Banque";
}

function assetClassLabel(assetClass: string) {
  if (assetClass === "crypto") return "Cryptoactifs";
  if (assetClass === "real_estate") return "Immobilier tokenisé";
  return assetClass === "brokerage" ? "Actions et titres" : "Autres investissements";
}

export default function InvestmentFlowsSummary() {
  const query = useBudgetInvestmentFlows();
  const summary = query.data;

  return (
    <section
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:p-5"
      aria-labelledby="investment-flows-title"
    >
      <div>
        <h2 id="investment-flows-title" className="text-base font-semibold">
          Investissements nets
        </h2>
        <p className="mt-1 max-w-3xl text-xs text-[var(--muted-foreground)]">
          Virements et dépôts vers les plateformes, moins les retraits reçus. Les montants restent
          séparés par devise.
        </p>
      </div>

      {query.isLoading ? (
        <div
          className="mt-4 h-24 rounded-lg skeleton-shimmer"
          aria-label="Calcul des flux d’investissement"
        />
      ) : query.isError ? (
        <p className="mt-4 rounded-lg border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted-foreground)]">
          Le calcul des mouvements d’investissement est temporairement indisponible.
        </p>
      ) : !summary || summary.plateformes.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted-foreground)]">
          <p>Aucun virement vers une plateforme détecté dans les relevés importés.</p>
          {summary?.plateformes_sans_historique.length ? (
            <p className="mt-1 text-xs">
              Sans historique importé : {summary.plateformes_sans_historique.slice(0, 8).join(", ")}
              {summary.plateformes_sans_historique.length > 8 ? "…" : ""}.
            </p>
          ) : null}
        </div>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            {summary.totaux_par_devise.map((total) => (
              <div
                key={total.devise}
                className="min-w-40 rounded-lg bg-[var(--muted)]/50 px-3 py-2.5"
              >
                <p className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                  Net investi · {total.devise}
                </p>
                <p className="mt-0.5 text-lg font-semibold tabular-nums">
                  {formatMoney(total.net, total.devise)}
                </p>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  {formatMoney(total.versements, total.devise)} versés −{" "}
                  {formatMoney(total.retraits, total.devise)} retirés
                </p>
              </div>
            ))}
          </div>

          <div className="mt-4 overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full min-w-[660px] text-left text-xs">
              <thead className="bg-[var(--muted)]/50 text-[var(--muted-foreground)]">
                <tr>
                  <th className="px-3 py-2 font-medium">Plateforme</th>
                  <th className="px-3 py-2 font-medium">Devise</th>
                  <th className="px-3 py-2 text-right font-medium">Versements</th>
                  <th className="px-3 py-2 text-right font-medium">Retraits reçus</th>
                  <th className="px-3 py-2 text-right font-medium">Net</th>
                  <th className="px-3 py-2 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {summary.plateformes.map((flow) => (
                  <tr key={`${flow.plateforme}-${flow.devise}`}>
                    <td className="px-3 py-2">
                      <p className="font-medium">{flow.plateforme}</p>
                      <p className="text-[10px] text-[var(--muted-foreground)]">
                        {assetClassLabel(flow.classe)}
                      </p>
                    </td>
                    <td className="px-3 py-2">{flow.devise}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatMoney(flow.versements, flow.devise)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatMoney(flow.retraits, flow.devise)}
                    </td>
                    <td className="px-3 py-2 text-right font-semibold tabular-nums">
                      {formatMoney(flow.net, flow.devise)}
                    </td>
                    <td className="px-3 py-2 text-[var(--muted-foreground)]">
                      {sourceLabel(flow.source)} · {flow.mouvements} mouvement
                      {flow.mouvements > 1 ? "s" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-[11px] text-[var(--muted-foreground)]">
            {summary.regle_dedoublonnage} Les achats, ventes, dividendes et intérêts à l’intérieur
            d’un compte ne sont pas comptés comme des dépôts ou retraits.
          </p>
          <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">
            Doublons évités : {summary.mouvements_bancaires_associes_plateforme} ligne(s)
            bancaire(s) rapprochée(s) au relevé de plateforme, {summary.doublons_bancaires_ecartes}{" "}
            doublon(s) bancaire(s) exact(s), {summary.doublons_bancaires_intercomptes_ecartes}{" "}
            doublon(s) entre comptes et {summary.doublons_plateformes_ecartes} doublon(s) exact(s)
            de plateforme.
          </p>

          {summary.plateformes_sans_historique.length > 0 && (
            <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">
              Aucun mouvement importé détecté pour :{" "}
              {summary.plateformes_sans_historique.slice(0, 8).join(", ")}
              {summary.plateformes_sans_historique.length > 8
                ? ` et ${summary.plateformes_sans_historique.length - 8} autre(s)`
                : ""}
              . Le total couvre seulement les relevés disponibles.
            </p>
          )}
        </>
      )}
    </section>
  );
}
