"use client";

import { AlertCircle, CheckCircle2, ShoppingCart } from "lucide-react";
import Link from "next/link";
import type {
  CartFillJob,
  CartPlanResponse,
  FenetreDayPlan,
  FenetreGenerateJob,
  ShoppingItem,
  WindowPlanResponse,
} from "@/lib/sante";
import { Button } from "@/components/ui/button";

type GenerateControlsProps = {
  poids: string;
  generating: boolean;
  hasWindow: boolean;
  onPoidsChange: (value: string) => void;
  onGenerate: (force?: boolean, refreshPrices?: boolean) => void;
};

export function FenetreGenerateControls({
  poids, generating, hasWindow, onPoidsChange, onGenerate,
}: GenerateControlsProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="text-sm">
        Poids (kg)
        <input
          value={poids}
          onChange={(event) => onPoidsChange(event.target.value)}
          inputMode="decimal"
          className="ml-2 w-24 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] px-2 py-1"
        />
      </label>
      <button
        onClick={() => onGenerate(false)}
        disabled={generating}
        className="rounded-[var(--radius)] bg-[var(--primary)] px-3 py-1.5 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
      >
        {generating ? "Optimisation…" : "Générer la fenêtre"}
      </button>
      <button
        onClick={() => onGenerate(true, false)}
        disabled={generating}
        title="Ne lance pas de mise à jour des prix ; utilise uniquement le catalogue déjà enregistré."
        className="rounded-[var(--radius)] border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50"
      >
        Générer avec les prix enregistrés
      </button>
      {hasWindow && (
        <button
          onClick={() => onGenerate(true)}
          disabled={generating}
          className="rounded-[var(--radius)] bg-[var(--muted)] px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Régénérer
        </button>
      )}
    </div>
  );
}

function GenerationMessage({ job }: { job: FenetreGenerateJob }) {
  return <span>{job.status === "failed" ? `⚠ ${job.error || job.message}` : job.message || "Préparation du catalogue…"}</span>;
}

function numberOr(value: number | null | undefined, fallback = 0) { return value ?? fallback; }
function listLength(value: unknown[] | null | undefined) { return value?.length ?? 0; }
function maxAttempts(value: number | null | undefined) { return value ?? "∞"; }

function GenerationStopButton({ job, onStop }: { job: FenetreGenerateJob; onStop: () => void }) {
  const active = ["queued", "running"].includes(job.status);
  if (!active) return null;
  return (
    <button
      type="button"
      onClick={onStop}
      disabled={job.stop_requested}
      className="text-[var(--destructive)] hover:underline disabled:opacity-50 disabled:no-underline"
    >
      {job.stop_requested ? "Arrêt demandé…" : "⏹ Arrêter"}
    </button>
  );
}

function GenerationMetrics({ job }: { job: FenetreGenerateJob }) {
  const simplified = job.phase === "simplification";
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {simplified ? (
        <>
          <span>Simplification {numberOr(job.prune_attempt)}/{numberOr(job.prune_total)}</span>
          <span>{listLength(job.removed_foods)} aliments retirés</span>
        </>
      ) : (
        <>
          <span>Essai {numberOr(job.attempt)}/{maxAttempts(job.max_attempts)}</span>
          <span>{numberOr(job.solutions_found)} solutions</span>
          <span>{numberOr(job.pareto_solutions)} sur la frontière</span>
          <span>Température {numberOr(job.temperature).toFixed(2)}</span>
        </>
      )}
      <GenerationHighlights job={job} />
    </div>
  );
}

function GenerationHighlights({ job }: { job: FenetreGenerateJob }) {
  return <><BestCoverage value={job.best_coverage} /><BestCost value={job.best_cost} /><BestRatio value={job.best_ratio} /></>;
}
function BestCoverage({ value }: { value?: number | null }) {
  if (value == null) return null;
  return <span>Équilibre {(value * 100).toFixed(1)}%</span>;
}
function BestCost({ value }: { value?: number | null }) {
  if (value == null) return null;
  return <span>{value.toFixed(2)} $</span>;
}
function BestRatio({ value }: { value?: number | null }) {
  if (value == null) return null;
  return <span>Meilleur ratio {value.toFixed(3)} pt/$</span>;
}

function GenerationBestItems({ job }: { job: FenetreGenerateJob }) {
  if (!job.best_items?.length) return null;
  return (
    <details className="rounded border border-[var(--border)] px-2 py-1.5">
      <summary className="cursor-pointer text-xs font-medium">Voir le meilleur candidat ({job.best_items.length} aliments)</summary>
      <ul className="mt-1 grid gap-x-4 text-xs sm:grid-cols-2 lg:grid-cols-3">
        {job.best_items.map((item) => (
          <li key={item.aliment} className="flex justify-between gap-2">
            <span>{item.aliment}</span>
            <span className="tabular-nums">{item.quantite_g.toFixed(0)} g</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function GenerationProgress({ job }: { job: FenetreGenerateJob }) {
  const progress = job.phase === "simplification"
    ? (numberOr(job.prune_attempt) / Math.max(1, numberOr(job.prune_total, 1))) * 100
    : numberOr(job.convergence) * 100;
  return (
    <div className="mt-2 space-y-1.5">
      <GenerationMetrics job={job} />
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--muted)]">
        <div className="h-full rounded-full bg-[var(--primary)] transition-[width] duration-500" style={{ width: `${Math.max(2, Math.min(100, progress))}%` }} />
      </div>
      <GenerationConvergence job={job} />
      <GenerationBestItems job={job} />
    </div>
  );
}

function GenerationConvergence({ job }: { job: FenetreGenerateJob }) {
  if (job.phase === "simplification") return null;
  return <p className="text-xs">Convergence : {numberOr(job.stagnation)}/{numberOr(job.patience)} essais sans nouvelle solution dominante.</p>;
}

function GenerationProgressSlot({ running, job }: { running: boolean; job: FenetreGenerateJob }) {
  if (!running || (numberOr(job.attempt) <= 0 && job.phase !== "simplification")) return null;
  return <GenerationProgress job={job} />;
}

function GenerationKeepAlive({ running }: { running: boolean }) {
  if (!running) return null;
  return <p className="mt-1 text-xs">Tu peux quitter cet onglet : la recherche continue côté serveur.</p>;
}

export function FenetreGenerationStatus({ job, onStop }: { job: FenetreGenerateJob | null; onStop: () => void }) {
  if (!job) return null;
  const running = ["queued", "running"].includes(job.status);
  if (!running && job.status !== "failed") return null;
  return <GenerationStatusBox job={job} running={running} onStop={onStop} />;
}

function GenerationStatusBox({ job, running, onStop }: { job: FenetreGenerateJob; running: boolean; onStop: () => void }) {
  return (
    <div className={`rounded-[var(--radius)] border border-[var(--border)] px-3 py-2 text-sm ${job.status === "failed" ? "text-[var(--destructive)]" : "text-[var(--muted-foreground)]"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GenerationMessage job={job} />
        <GenerationStopButton job={job} onStop={onStop} />
      </div>
      <GenerationProgressSlot running={running} job={job} />
      <GenerationKeepAlive running={running} />
    </div>
  );
}

type MacroSummary = { key: string; label: string; unit: string; total: number; target: number };

function MacroSummaryCards({ macros }: { macros: MacroSummary[] }) {
  return (
    <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
      {macros.filter((macro) => macro.target > 0).map((macro) => {
        const pct = macro.total / macro.target * 100;
        return <div key={macro.key} className="rounded bg-[var(--muted)] px-2 py-1.5"><span>{macro.label}</span>{" "}<b>{macro.total.toFixed(0)} / {macro.target.toFixed(0)} {macro.unit}</b>{" "}<span className="text-[var(--muted-foreground)]">({pct.toFixed(0)}%)</span></div>;
      })}
    </div>
  );
}

export function FenetreScoreSection({ win, macros, macroBalance, globalBalance }: {
  win: WindowPlanResponse; macros: MacroSummary[]; macroBalance: number; globalBalance: number;
}) {
  return (
    <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
      <h3 className="mb-2 font-medium">Score</h3>
      <div className="flex flex-wrap gap-6 text-sm">
        <div><b>{win.score.pct_micros_atteints.toFixed(1)}%</b> équilibre micros</div>
        <div><b>{(macroBalance * 100).toFixed(1)}%</b> équilibre macros</div>
        <div><b>{(globalBalance * 100).toFixed(1)}%</b> équilibre global</div>
        <div>Panier complet <b>{win.score.cout_total.toFixed(2)} $</b></div>
        <div title="Stock périssable : 0 %; stock durable : 50 %; quantité au-delà du stock : 100 %.">Coût optimisé <b>{(win.score.cout_optimise ?? win.score.cout_total).toFixed(2)} $</b></div>
        <div>À payer <b>{win.score.cout_a_payer.toFixed(2)} $</b></div>
        <div>Ratio <b>{win.score.ratio.toFixed(3)}</b> pt/$</div>
      </div>
      <MacroSummaryCards macros={macros} />
      <UnderCoveredMicros values={win.score.sous_couverts} />
    </section>
  );
}

function UnderCoveredMicros({ values }: { values: string[] }) {
  if (!values.length) return null;
  return <p className="mt-2 text-xs text-[var(--muted-foreground)]">Sous-couverts:{" "}{values.map((value) => <span key={value} className="mr-1 rounded bg-[var(--muted)] px-1.5 py-0.5">{value}</span>)}</p>;
}

function ShoppingItemBadges({ item }: { item: ShoppingItem }) {
  return (
    <>
      {item.promo && <span className="rounded bg-[var(--primary)] px-1.5 py-0.5 text-xs text-[var(--primary-foreground)]">promo</span>}
      {item.prix_verifie && <span className="inline-flex items-center gap-1 rounded bg-[var(--success-muted)] px-1.5 py-0.5 text-xs text-[var(--success)]"><CheckCircle2 className="h-3 w-3" aria-hidden="true" /> prix vérifié</span>}
    </>
  );
}

function ShoppingItemQuantity({ item }: { item: ShoppingItem }) {
  if (item.a_acheter_g == null) return <span className="text-[var(--muted-foreground)]">{item.quantite_g.toFixed(0)} g</span>;
  const stock = item.dispo_g ? ` · ${item.dispo_g.toFixed(0)} g en stock` : "";
  return <span className="text-[var(--muted-foreground)]">{item.a_acheter_g.toFixed(0)} g à acheter{stock}</span>;
}

function ShoppingItemPrice({ item }: { item: ShoppingItem }) {
  return <span className="ml-auto tabular-nums">{item.prix != null ? `${item.prix.toFixed(2)} $` : "—"}</span>;
}

function ShoppingItemName({ item, checked }: { item: ShoppingItem; checked: boolean }) {
  return <span className={checked ? "line-through opacity-50" : ""}>{item.product_name ?? item.aliment}</span>;
}

function ShoppingItemFormat({ item }: { item: ShoppingItem }) {
  if (!item.format) return null;
  return <span className="text-[var(--muted-foreground)]">{item.format} × {item.qty ?? 1}</span>;
}

function ShoppingItemRow({ item, checked, onChecked }: { item: ShoppingItem; checked: boolean; onChecked: (value: boolean) => void }) {
  return (
    <li className="flex items-center gap-3 py-1.5 text-sm">
      <input type="checkbox" checked={checked} onChange={(event) => onChecked(event.target.checked)} />
      <ShoppingItemName item={item} checked={checked} />
      <ShoppingItemFormat item={item} />
      <ShoppingItemQuantity item={item} />
      <ShoppingItemBadges item={item} />
      <ShoppingItemPrice item={item} />
    </li>
  );
}

export function FenetreShoppingSection({ win, checked, onChecked }: {
  win: WindowPlanResponse; checked: Record<string, boolean>; onChecked: (aliment: string, value: boolean) => void;
}) {
  return (
    <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
      <h3 className="mb-2 font-medium">Liste de courses ({win.length} j)</h3>
      {win.shopping_date && <p className="mb-2 text-xs text-[var(--muted-foreground)]">Courses et cuisine le <strong className="text-[var(--foreground)]">{new Date(`${win.shopping_date}T00:00:00`).toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long" })}</strong> — rabais étudiant Super C de 10 % déjà déduit des prix.</p>}
      <p className="mb-2 text-xs text-[var(--muted-foreground)]">Ton stock est déduit de la liste — <Link href="/sante?tab=garde-manger" className="underline underline-offset-2">modifier le garde-manger</Link>.</p>
      <p className="mb-2 text-xs text-[var(--muted-foreground)]">Prix affiché par aliment : coût de la quantité réellement consommée. Les formats entiers à payer sont détaillés dans le panier Super C plus bas.</p>
      <ul className="divide-y divide-[var(--border)]">{win.shopping_list.map((item) => <ShoppingItemRow key={item.aliment} item={item} checked={!!checked[item.aliment]} onChecked={(value) => onChecked(item.aliment, value)} />)}</ul>
    </section>
  );
}

function ConsumptionLabel({ saving }: { saving: boolean }) { return <>{saving ? "…" : "✓ J'ai suivi le plan"}</>; }
function ConsumptionBadge({ saved }: { saved: boolean }) { return <>{saved ? "✓ conso enregistrée" : "⚠ conso non enregistrée"}</>; }

function DayPlanCard({ day, saved, saving, onConsume, onAdjust }: {
  day: FenetreDayPlan; saved: boolean; saving: boolean; onConsume: () => void; onAdjust: () => void;
}) {
  return (
    <div className="space-y-2 rounded-[var(--radius)] bg-[var(--muted)] p-2 text-xs">
      <div className="font-medium">{day.date} · {day.intensite}</div>
      {day.repas_travail?.map((meal) => <div key={meal.name} className="rounded border border-[var(--primary)]/30 bg-[var(--background)] p-2"><div className="font-medium">🍽️ Repas au travail — {meal.name}</div><div className="text-[var(--muted-foreground)]">Total {meal.price.toFixed(2)} $ avant taxes · coupon {meal.credit_couvert.toFixed(2)} $ · reste à payer {meal.reste_a_payer.toFixed(2)} $</div><div className="text-[var(--muted-foreground)]">~{meal.calories} kcal, {meal.proteines} g protéines · {meal.description}</div><div className="text-[var(--muted-foreground)]">Macros estimées; micros estimés à partir des ingrédients du plat.</div></div>)}
      <ul>{day.items.map((item) => <li key={item.aliment} className="flex justify-between"><span>{item.aliment}</span><span>{item.quantite_g.toFixed(0)} g</span></li>)}</ul>
      <div className="flex flex-wrap items-center gap-1.5 border-t border-[var(--border)] pt-1.5">
        <button onClick={onConsume} disabled={saving} className="rounded bg-[var(--success)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--success-foreground)] disabled:opacity-50"><ConsumptionLabel saving={saving} /></button>
        <button onClick={onAdjust} className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[11px] hover:bg-[var(--accent)]">✏️ Ajuster</button>
      </div>
      <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] ${saved ? "bg-[var(--success-muted)] text-[var(--success)]" : "bg-[var(--warning-muted)] text-[var(--warning)]"}`} title={saved ? "Conso enregistrée — la compensation J+1 fonctionnera." : "Conso non enregistrée pour ce jour."}><ConsumptionBadge saved={saved} /></span>
    </div>
  );
}

export function FenetreDaysSection({ days, savedDates, savingDate, error, onConsume, onAdjust }: {
  days: FenetreDayPlan[]; savedDates: Record<string, boolean>; savingDate: string | null; error: string | null;
  onConsume: (day: FenetreDayPlan) => void; onAdjust: (date: string) => void;
}) {
  return (
    <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
      <h3 className="mb-2 font-medium">Par jour</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{days.map((day) => <DayPlanCard key={day.date} day={day} saved={!!savedDates[day.date]} saving={savingDate === day.date} onConsume={() => onConsume(day)} onAdjust={() => onAdjust(day.date)} />)}</div>
      {error && <p className="mt-2 text-xs text-[var(--destructive)]">⚠ {error}</p>}
    </section>
  );
}

function CartItemLink({ item }: { item: CartPlanResponse["items"][number] }) {
  if (!item.href) return null;
  return <a href={`https://www.superc.ca${item.href}`} target="_blank" rel="noreferrer" className="text-[var(--primary)] underline">voir</a>;
}

function CartItemPrice({ item }: { item: CartPlanResponse["items"][number] }) {
  return <span className="ml-auto tabular-nums">{item.prix_estime != null ? `${(item.prix_estime * item.qty).toFixed(2)} $` : "—"}</span>;
}

function CartItemRow({ item }: { item: CartPlanResponse["items"][number] }) {
  return <li className="flex items-center gap-3 py-1.5"><span>{item.product_name ?? item.aliment}</span>{item.format && <span className="text-[var(--muted-foreground)]">{item.format}</span>}<span className="text-[var(--muted-foreground)]">× {item.qty}</span>{item.a_verifier && <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-xs">⚠ à vérifier</span>}<CartItemLink item={item} /><CartItemPrice item={item} /></li>;
}

function CartResults({ job }: { job: CartFillJob }) {
  if (!job.results.length) return null;
  return <ul className="mt-2 space-y-1 text-xs">{job.results.map((result) => <li key={`${result.aliment}-${result.status}`} className="flex items-start gap-1.5">{result.status === "added" || result.status === "already_present" ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" aria-hidden="true" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--warning)]" aria-hidden="true" />}<span><b>{result.product_name ?? result.aliment}</b> — {result.message}</span></li>)}</ul>;
}

function CartProgress({ job }: { job: CartFillJob }) {
  const percent = job.total ? (job.current / job.total) * 100 : 0;
  return <div className="mt-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--muted)] p-3" aria-live="polite"><div className="flex items-center justify-between gap-3 text-xs"><span className="font-medium">{job.message}</span><span className="tabular-nums">{job.current}/{job.total}</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--background)]" role="progressbar" aria-label="Progression du panier Super C" aria-valuemin={0} aria-valuemax={job.total} aria-valuenow={job.current}><div className="h-full bg-[var(--primary)] transition-[width] duration-200" style={{ width: `${percent}%` }} /></div>{job.status === "awaiting_user" && <p className="mt-2 text-xs text-[var(--warning)]">Termine la vérification de sécurité Super C dans Chrome. Le remplissage reprendra automatiquement.</p>}<CartResults job={job} /></div>;
}

export function FenetreCartSection({ plan, job, pending, error, onStart }: {
  plan: CartPlanResponse | undefined; job: CartFillJob | null; pending: boolean; error: boolean; onStart: () => void;
}) {
  if (!plan) return <CartEmptyState />;
  if (plan.items.length === 0) return <CartEmptyState />;
  const blocked = Boolean(job && ["queued", "running", "awaiting_user"].includes(job.status));
  return (
    <section className="rounded-[var(--radius)] border border-[var(--border)] p-4">
      <h3 className="mb-2 font-medium">Panier Super C</h3>
      <ul className="divide-y divide-[var(--border)] text-sm">{plan.items.map((item) => <CartItemRow key={item.aliment} item={item} />)}</ul>
      <div className="mt-2 text-sm">Total du panier <b>{plan.total_estime.toFixed(2)} $</b></div>
      <div className="mt-3 flex flex-wrap items-center gap-3"><Button type="button" size="sm" loading={pending} disabled={blocked} onClick={onStart}><ShoppingCart className="h-4 w-4" aria-hidden="true" />Ajouter au panier Super C</Button><span className="text-xs text-[var(--muted-foreground)]">Utilise une fenêtre Chrome dédiée et conserve les produits déjà présents.</span></div>
      <CartError visible={error} />
      <CartProgressSlot job={job} />
    </section>
  );
}

function CartEmptyState() {
  return <section className="rounded-[var(--radius)] border border-[var(--border)] p-4"><h3 className="mb-2 font-medium">Panier Super C</h3><p className="text-xs text-[var(--muted-foreground)]">Aucun produit à préparer.</p></section>;
}

function CartError({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return <p role="alert" className="mt-2 flex items-center gap-1.5 text-xs text-[var(--destructive)]"><AlertCircle className="h-4 w-4" aria-hidden="true" />Impossible de démarrer le remplissage.</p>;
}

function CartProgressSlot({ job }: { job: CartFillJob | null }) {
  if (!job) return null;
  return <CartProgress job={job} />;
}

export function FenetreWindowSections({
  win, macros, macroBalance, globalBalance, checked, savedDates, savingDate, consoError,
  cartPlan, cartJob, cartPending, cartError, onChecked, onConsume, onAdjust, onStartCart,
}: {
  win: WindowPlanResponse; macros: MacroSummary[]; macroBalance: number; globalBalance: number;
  checked: Record<string, boolean>; savedDates: Record<string, boolean>; savingDate: string | null;
  consoError: string | null; cartPlan: CartPlanResponse | undefined; cartJob: CartFillJob | null;
  cartPending: boolean; cartError: boolean; onChecked: (aliment: string, value: boolean) => void;
  onConsume: (day: FenetreDayPlan) => void; onAdjust: (date: string) => void; onStartCart: () => void;
}) {
  return (
    <>
      {win.warning && <p className="rounded-[var(--radius)] border border-[var(--border)] px-3 py-2 text-sm text-[var(--destructive)]">⚠ {win.warning}</p>}
      <FenetreScoreSection win={win} macros={macros} macroBalance={macroBalance} globalBalance={globalBalance} />
      <FenetreShoppingSection win={win} checked={checked} onChecked={onChecked} />
      <FenetreDaysSection days={win.jours} savedDates={savedDates} savingDate={savingDate} error={consoError} onConsume={onConsume} onAdjust={onAdjust} />
      <FenetreCartSection plan={cartPlan} job={cartJob} pending={cartPending} error={cartError} onStart={onStartCart} />
    </>
  );
}
