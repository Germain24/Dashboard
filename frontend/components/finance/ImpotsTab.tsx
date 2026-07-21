"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Calculator,
  CheckCircle2,
  ChevronRight,
  Info,
  ListFilter,
  ReceiptText,
  RefreshCw,
  Settings2,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useCalculImpots, useVentesImpots } from "@/lib/queries/finance";
import type { RegimeTax } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const eur = (value: number) =>
  new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);

export function ImpotsTab() {
  const currentYear = new Date().getFullYear();
  const years = useMemo(
    () => Array.from({ length: 7 }, (_, index) => currentYear - index),
    [currentYear],
  );
  const reduceMotion = useReducedMotion();
  const [year, setYear] = useState(currentYear);
  const [otherIncome, setOtherIncome] = useState(0);
  const [parts, setParts] = useState(1);
  const [priorLosses, setPriorLosses] = useState(0);
  const [priorLossYear, setPriorLossYear] = useState(currentYear - 1);
  const [eligibleDividends, setEligibleDividends] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);

  const taxQuery = useCalculImpots({
    annee: year,
    autres_revenus: otherIncome,
    parts,
    moins_values_anterieures: priorLosses,
    moins_values_anterieures_annee: priorLosses > 0 ? priorLossYear : undefined,
    dividendes_eligibles_abattement: eligibleDividends,
  });
  const salesQuery = useVentesImpots({ annee: year }, detailOpen);
  const data = taxQuery.data;

  return (
    <div className="space-y-5">
      <section className="glass-card rounded-[var(--radius-lg)] p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-[var(--radius)] bg-[var(--accent)] text-[var(--foreground)]">
                <ReceiptText className="h-4 w-4" aria-hidden />
              </span>
              <div>
                <h2 className="text-base font-semibold text-[var(--foreground)]">Estimation fiscale CTO</h2>
                <p className="text-xs text-[var(--muted-foreground)]">Résidence fiscale française · montants en EUR</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--muted-foreground)]">
              <span className="rounded-[var(--radius-sm)] border border-[var(--glass-border)] px-2 py-1">Prix moyen pondéré</span>
              <span className="rounded-[var(--radius-sm)] border border-[var(--glass-border)] px-2 py-1">CTO uniquement</span>
              {data && (
                <span className="flex items-center gap-1 rounded-[var(--radius-sm)] border border-[var(--success)]/30 bg-[var(--success-muted)]/45 px-2 py-1 text-[var(--success-foreground)]">
                  <CheckCircle2 className="h-3 w-3" aria-hidden />
                  {data.data_quality.ventes_calculables}/{data.data_quality.ventes_total} ventes vérifiées
                </span>
              )}
            </div>
          </div>

          <label className="flex shrink-0 items-center gap-3 text-sm">
            <span className="text-[var(--muted-foreground)]">Année fiscale</span>
            <select
              value={year}
              onChange={(event) => {
                const nextYear = Number(event.target.value);
                setYear(nextYear);
                setDetailOpen(false);
                setPriorLossYear((value) => Math.min(value, nextYear - 1));
              }}
              className="glass-inset h-9 rounded-[var(--radius)] border border-[var(--border)] px-3 font-mono tabular-nums text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
            >
              {years.map((item) => (
                <option key={item} value={item}>{item}{item === currentYear ? " · en cours" : ""}</option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={() => setSettingsOpen((open) => !open)}
          aria-expanded={settingsOpen}
          className="mt-4 flex w-full items-center justify-between gap-3 border-t border-[var(--glass-border)] pt-3 text-left text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
        >
          <span className="flex items-center gap-2"><Settings2 className="h-4 w-4" aria-hidden />Hypothèses du foyer</span>
          <ChevronRight className={`h-4 w-4 transition-transform duration-200 ${settingsOpen ? "rotate-90" : ""}`} aria-hidden />
        </button>

        {settingsOpen && (
          <div className="mt-4 grid gap-4 border-t border-[var(--glass-border)] pt-4 sm:grid-cols-2 xl:grid-cols-4 animate-fade-in">
            <NumberField label="Autres revenus imposables" value={otherIncome} min={0} step={100} suffix="€" onCommit={setOtherIncome} />
            <NumberField label="Parts fiscales" value={parts} min={0.5} max={20} step={0.5} onCommit={setParts} />
            <NumberField label="Moins-values reportées" value={priorLosses} min={0} step={10} suffix="€" onCommit={setPriorLosses} />
            <NumberField label="Année d'origine du report" value={priorLossYear} min={year - 10} max={year - 1} step={1} disabled={priorLosses <= 0} onCommit={setPriorLossYear} />
            <div className="flex items-start gap-2.5 text-sm sm:col-span-2 xl:col-span-4">
              <input
                id="eligible-dividends"
                type="checkbox"
                checked={eligibleDividends}
                onChange={(event) => setEligibleDividends(event.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[var(--border)] accent-[var(--primary)]"
              />
              <span>
                <label htmlFor="eligible-dividends" className="block cursor-pointer font-medium text-[var(--foreground)]">Appliquer l'abattement de 40 % aux dividendes éligibles</label>
                <span className="block text-xs text-[var(--muted-foreground)]">Les intérêts et paiements compensatoires restent exclus de l'abattement.</span>
              </span>
            </div>
          </div>
        )}
      </section>

      {taxQuery.isLoading && <TaxSkeleton />}

      {taxQuery.isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[var(--destructive)]/30 bg-[var(--destructive-muted)]/25 p-4">
          <span className="flex items-center gap-2 text-sm text-[var(--destructive)]">
            <AlertTriangle className="h-4 w-4" aria-hidden />
            Le calcul fiscal n'a pas pu être chargé.
          </span>
          <Button size="sm" variant="ghost" onClick={() => void taxQuery.refetch()}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />Réessayer
          </Button>
        </div>
      )}

      {data && (
        <motion.div
          key={`${year}-${otherIncome}-${parts}-${priorLosses}-${eligibleDividends}`}
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.24 }}
          className="space-y-5"
        >
          {data.avertissements.map((warning) => (
            <div key={warning} className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--warning)]/25 bg-[var(--warning-muted)]/35 p-3 text-xs leading-relaxed text-[var(--warning-foreground)]">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{warning}</span>
            </div>
          ))}

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryStat
              label={`Plus-value réalisée ${year}`}
              value={eur(data.gain_brut)}
              detail={`${data.data_quality.ventes_total} cession${data.data_quality.ventes_total > 1 ? "s" : ""}`}
              tone={data.gain_brut > 0 ? "positive" : data.gain_brut < 0 ? "negative" : undefined}
              onClick={() => setDetailOpen(true)}
            />
            <SummaryStat label="Plus-value imposable" value={eur(data.gain_net_imposable)} detail="Après imputation des moins-values" strong />
            <SummaryStat
              label="Revenus mobiliers bruts"
              value={eur(data.revenus_mobiliers_bruts)}
              detail={`${eur(data.dividendes_nets)} dividendes nets · ${eur(data.interets_nets)} intérêts`}
            />
            <SummaryStat label="Moins-values à reporter" value={eur(data.report_moins_values_restant)} detail="Imputables pendant 10 ans" tone={data.report_moins_values_restant > 0 ? "warning" : undefined} />
          </div>

          <section>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--foreground)]">Comparaison des régimes</h3>
                <p className="text-xs text-[var(--muted-foreground)]">Impôt français brut avant éventuel crédit d'impôt étranger</p>
              </div>
              {taxQuery.isFetching && !taxQuery.isLoading && (
                <span className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]"><RefreshCw className="h-3 w-3 animate-spin" aria-hidden />Actualisation</span>
              )}
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <RegimeCard
                title={`PFU ${data.pfu.taux_ir_pct ?? 12.8}% + ${data.pfu.taux_sociaux_pct}%`}
                subtitle="Option appliquée par défaut"
                regime={data.pfu}
                lower={data.recommande === "pfu"}
              />
              <RegimeCard
                title="Barème progressif"
                subtitle={`Barème revenus ${data.bareme_reference_revenus}${data.bareme_provisoire ? " · provisoire" : ""}`}
                regime={data.bareme}
                lower={data.recommande === "bareme"}
              />
            </div>
            {data.retenue_source_etrangere > 0 && (
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--glass-border)] pt-3 text-sm">
                <span className="text-[var(--muted-foreground)]">Retenues étrangères déjà prélevées</span>
                <strong className="font-mono tabular-nums text-[var(--warning-foreground)]">{eur(data.retenue_source_etrangere)}</strong>
              </div>
            )}
          </section>

          {Object.keys(data.historique_par_annee).length > 1 && (
            <section className="glass-card overflow-hidden rounded-[var(--radius-lg)]">
              <div className="border-b border-[var(--glass-border)] px-4 py-3">
                <h3 className="text-sm font-semibold">Suivi des moins-values</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[540px] text-sm">
                  <thead className="bg-[var(--field)] text-left text-xs text-[var(--muted-foreground)]">
                    <tr><th className="px-4 py-2 font-medium">Année</th><th className="px-4 py-2 text-right font-medium">Résultat réalisé</th><th className="px-4 py-2 text-right font-medium">Imposable</th><th className="px-4 py-2 text-right font-medium">Report restant</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.historique_par_annee).map(([itemYear, row]) => (
                      <tr key={itemYear} className="border-t border-[var(--glass-border)] first:border-0">
                        <td className="px-4 py-2.5 font-medium">{itemYear}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">{eur(row.gain_brut)}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">{eur(row.gain_net_imposable)}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">{eur(row.report_apres)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <p className="flex items-start gap-2 text-[11px] leading-relaxed text-[var(--muted-foreground)]">
            <Calculator className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            Estimation indicative : PEA, décote, plafonnement du quotient familial, CEHR/CDHR, autres revenus mobiliers et crédits d'impôt conventionnels ne sont pas calculés. L'IFU du courtier et le simulateur DGFiP restent les références déclaratives.
          </p>
        </motion.div>
      )}

      <SalesDialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        year={year}
        query={salesQuery}
      />
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  suffix,
  disabled,
  onCommit,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  step: number;
  suffix?: string;
  disabled?: boolean;
  onCommit: (value: number) => void;
}) {
  const commit = (input: HTMLInputElement) => {
    const parsed = Number(input.value);
    const safe = Number.isFinite(parsed) ? Math.min(max ?? Number.POSITIVE_INFINITY, Math.max(min, parsed)) : value;
    input.value = String(safe);
    onCommit(safe);
  };
  return (
    <label className={`text-sm ${disabled ? "opacity-50" : ""}`}>
      <span className="block text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className="relative mt-1 block">
        <input
          type="number"
          key={value}
          defaultValue={value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onBlur={(event) => commit(event.currentTarget)}
          onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }}
          className={`glass-inset h-9 w-full rounded-[var(--radius)] border border-[var(--border)] px-3 font-mono tabular-nums text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)] ${suffix ? "pr-8" : ""}`}
        />
        {suffix && <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-[var(--muted-foreground)]">{suffix}</span>}
      </span>
    </label>
  );
}

function SummaryStat({
  label,
  value,
  detail,
  tone,
  strong,
  onClick,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "positive" | "negative" | "warning";
  strong?: boolean;
  onClick?: () => void;
}) {
  const toneClass = tone === "positive" ? "text-[var(--success-foreground)]" : tone === "negative" ? "text-[var(--destructive)]" : tone === "warning" ? "text-[var(--warning-foreground)]" : "text-[var(--foreground)]";
  const content = (
    <>
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <strong className={`mt-1 block font-mono tabular-nums ${strong ? "text-xl" : "text-lg"} ${toneClass}`}>{value}</strong>
      <span className="mt-1 block text-[11px] text-[var(--muted-foreground)]">{detail}</span>
    </>
  );
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="glass-card group min-h-28 rounded-[var(--radius-lg)] p-4 text-left transition-[transform,border-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-[var(--ring)]/30 hover:shadow-[var(--shadow-md)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]">
        {content}
        <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-[var(--foreground)]">Voir les ventes <ChevronRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" aria-hidden /></span>
      </button>
    );
  }
  return <div className="glass-card min-h-28 rounded-[var(--radius-lg)] p-4">{content}</div>;
}

function RegimeCard({
  title,
  subtitle,
  regime,
  lower,
}: {
  title: string;
  subtitle: string;
  regime: RegimeTax;
  lower: boolean;
}) {
  return (
    <article className={`glass-card rounded-[var(--radius-lg)] p-4 transition-colors ${lower ? "border-[var(--success)]/45 bg-[var(--success-muted)]/20" : ""}`}>
      <div className="flex min-h-10 items-start justify-between gap-3">
        <div><h4 className="text-sm font-semibold">{title}</h4><p className="text-[11px] text-[var(--muted-foreground)]">{subtitle}</p></div>
        {lower && <span className="shrink-0 rounded-[var(--radius-sm)] bg-[var(--success-muted)] px-2 py-1 text-[10px] font-semibold text-[var(--success-foreground)]">Montant inférieur</span>}
      </div>
      <div className="my-4 font-mono text-2xl font-semibold tabular-nums text-[var(--foreground)]">{eur(regime.total)}</div>
      <dl className="space-y-2 border-t border-[var(--glass-border)] pt-3 text-xs">
        <div className="flex justify-between gap-4"><dt className="text-[var(--muted-foreground)]">Impôt sur le revenu</dt><dd className="font-mono tabular-nums">{eur(regime.ir)}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-[var(--muted-foreground)]">Prélèvements sociaux</dt><dd className="font-mono tabular-nums">{eur(regime.social)}</dd></div>
        {(regime.abattement_dividendes ?? 0) > 0 && <div className="flex justify-between gap-4"><dt className="text-[var(--muted-foreground)]">Abattement dividendes</dt><dd className="font-mono tabular-nums">-{eur(regime.abattement_dividendes ?? 0)}</dd></div>}
        {(regime.csg_deductible_annee_suivante ?? 0) > 0 && <div className="flex justify-between gap-4"><dt className="text-[var(--muted-foreground)]">CSG déductible l'année suivante</dt><dd className="font-mono tabular-nums">{eur(regime.csg_deductible_annee_suivante ?? 0)}</dd></div>}
      </dl>
    </article>
  );
}

function TaxSkeleton() {
  return (
    <div className="space-y-4" aria-label="Calcul fiscal en cours">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="skeleton-shimmer h-28 rounded-[var(--radius-lg)]" />)}</div>
      <div className="grid gap-3 lg:grid-cols-2"><div className="skeleton-shimmer h-56 rounded-[var(--radius-lg)]" /><div className="skeleton-shimmer h-56 rounded-[var(--radius-lg)]" /></div>
    </div>
  );
}

function SalesDialog({
  open,
  onClose,
  year,
  query,
}: {
  open: boolean;
  onClose: () => void;
  year: number;
  query: ReturnType<typeof useVentesImpots>;
}) {
  const sales = query.data?.ventes;
  return (
    <Dialog open={open} onClose={onClose} className="max-w-5xl !bg-[var(--background)]">
      <DialogHeader onClose={onClose}>
        <DialogTitle>Ventes réalisées en {year}</DialogTitle>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">Coût fiscal au prix moyen pondéré, compte par compte</p>
      </DialogHeader>
      <DialogBody className="pb-5">
        {query.isLoading && <div className="skeleton-shimmer h-48 rounded-[var(--radius-lg)]" />}
        {query.isError && (
          <div role="alert" className="flex items-center justify-between gap-3 rounded-[var(--radius)] border border-[var(--destructive)]/30 p-3 text-sm text-[var(--destructive)]">
            <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" aria-hidden />Détail indisponible.</span>
            <Button size="sm" variant="ghost" onClick={() => void query.refetch()}><RefreshCw className="h-3.5 w-3.5" aria-hidden />Réessayer</Button>
          </div>
        )}
        {sales && sales.length === 0 && (
          <div className="grid min-h-40 place-items-center rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] text-center">
            <div><ListFilter className="mx-auto mb-2 h-5 w-5 text-[var(--muted-foreground)]" aria-hidden /><p className="text-sm font-medium">Aucune vente en {year}</p><p className="text-xs text-[var(--muted-foreground)]">Les plus-values latentes ne sont pas imposées ici.</p></div>
          </div>
        )}
        {sales && sales.length > 0 && (
          <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--glass-border)]">
            <table className="w-full min-w-[840px] text-sm">
              <thead className="sticky top-0 bg-[var(--card)] text-left text-xs text-[var(--muted-foreground)]">
                <tr><th className="px-3 py-2 font-medium">Date</th><th className="px-3 py-2 font-medium">Titre</th><th className="px-3 py-2 text-right font-medium">Quantité</th><th className="px-3 py-2 text-right font-medium">PMP</th><th className="px-3 py-2 text-right font-medium">Prix de vente</th><th className="px-3 py-2 text-right font-medium">Produit net</th><th className="px-3 py-2 text-right font-medium">Résultat</th></tr>
              </thead>
              <tbody>
                {sales.map((sale, index) => (
                  <tr key={`${sale.date}-${sale.ticker}-${index}`} className="border-t border-[var(--glass-border)]">
                    <td className="whitespace-nowrap px-3 py-2.5">{sale.date.slice(0, 10)}</td>
                    <td className="px-3 py-2.5"><span className="block font-mono text-xs font-medium">{sale.ticker}</span><span className="block text-[10px] text-[var(--muted-foreground)]">{sale.broker}</span></td>
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums">{sale.quantite}</td>
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums">{eur(sale.prix_achat_moyen)}</td>
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums">{eur(sale.prix_vente)}</td>
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums">{sale.produit_net == null ? "—" : eur(sale.produit_net)}</td>
                    <td className={`px-3 py-2.5 text-right font-mono tabular-nums ${sale.plus_value == null ? "text-[var(--warning-foreground)]" : sale.plus_value >= 0 ? "text-[var(--success-foreground)]" : "text-[var(--destructive)]"}`} title={sale.raison ?? undefined}>{sale.plus_value == null ? sale.raison : eur(sale.plus_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DialogBody>
    </Dialog>
  );
}
