import type {
  CategoryShare,
  CashFlowForecast,
  EnvelopeStatus,
  MonthTrend,
  Recurring,
  RecurringProjection,
  RollingSummary,
  SavingsGoal,
  SubscriptionAlerts as SubscriptionAlertsData,
  TagSpend,
} from "@/lib/budget";
import { CategoryShareChart, Donut, TrendChart } from "./charts";
import { SubscriptionAlerts } from "./SubscriptionAlerts";
import { StaggerGroup, StaggerItem } from "@/lib/motion/Stagger";
import { CHART_SERIES } from "@/lib/design/colors";

const formatCAD = (value: number) =>
  new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD" }).format(value ?? 0);

export function BudgetLoadingState() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map((index) => (
          <div
            key={index}
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 h-20 skeleton-shimmer"
          />
        ))}
      </div>
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] h-48 skeleton-shimmer" />
    </div>
  );
}

function BudgetAlert({
  over,
  warn,
  categoryName,
}: {
  over: EnvelopeStatus[];
  warn: EnvelopeStatus[];
  categoryName: (id: number) => string;
}) {
  if (over.length === 0 && warn.length === 0) return null;
  const alert = budgetAlertData(over, warn);
  const entries = [...over, ...warn];
  return (
    <div
      className="rounded-xl border p-3 text-sm animate-fade-in-up"
      style={{
        borderColor: alert.color,
        background: `color-mix(in srgb, ${alert.color} 10%, transparent)`,
      }}
    >
      <p className="font-medium" style={{ color: alert.color }}>
        {alert.title}
      </p>
      <p className="mt-0.5 text-[var(--muted-foreground)]">
        {entries.map((entry) => categoryName(entry.category_id)).join(" · ")}
      </p>
    </div>
  );
}

function budgetAlertData(over: EnvelopeStatus[], warn: EnvelopeStatus[]) {
  const isOver = over.length > 0;
  const count = isOver ? over.length : warn.length;
  const color = isOver ? "var(--destructive)" : "var(--warning)";
  return { color, title: alertTitle(isOver, count) };
}

function pluralSuffix(count: number) {
  return count > 1 ? "s" : "";
}

function alertTitle(isOver: boolean, count: number) {
  const suffix = pluralSuffix(count);
  return isOver
    ? `⚠ ${count} catégorie${suffix} dépassée${suffix}`
    : `${count} catégorie${suffix} proche${suffix} de la limite`;
}

function SavingsGoalCard({
  savings,
  goalInput,
  onGoalInput,
  onSave,
}: {
  savings: SavingsGoal | null;
  goalInput: string;
  onGoalInput: (value: string) => void;
  onSave: () => void;
}) {
  if (!savings) return null;
  return <SavingsGoalContent savings={savings} goalInput={goalInput} onGoalInput={onGoalInput} onSave={onSave} />;
}

function SavingsGoalContent({
  savings,
  goalInput,
  onGoalInput,
  onSave,
}: {
  savings: SavingsGoal;
  goalInput: string;
  onGoalInput: (value: string) => void;
  onSave: () => void;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Objectif d&apos;épargne mensuel</h2>
        <div className="flex items-center gap-1">
          <input
            type="number"
            step="50"
            min="0"
            placeholder={savings.objectif > 0 ? String(savings.objectif) : "montant"}
            value={goalInput}
            onChange={(event) => onGoalInput(event.target.value)}
            aria-label="Objectif d'épargne (CAD)"
            className="w-24 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          />
          <button
            onClick={onSave}
            className="rounded bg-[var(--primary)] px-2 py-1 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            Définir
          </button>
        </div>
      </div>
      {savings.objectif > 0 ? (
        <>
          <div className="mb-1.5 flex items-center justify-between text-sm">
            <span className="font-mono">{formatCAD(savings.epargne)}</span>
            <span className="text-xs text-[var(--muted-foreground)]">
              / {formatCAD(savings.objectif)} · {savings.progress_pct}%
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
            <div
              className="h-full rounded-full bar-fill"
              style={{
                width: `${Math.min(100, savings.progress_pct)}%`,
                background: savings.progress_pct >= 100 ? "var(--success)" : "var(--ring)",
              }}
            />
          </div>
        </>
      ) : (
        <p className="text-xs text-[var(--muted-foreground)]">
          Aucun objectif défini. Saisis un montant à épargner ce mois.
        </p>
      )}
    </div>
  );
}

function SummaryCard({ label, value, tone, detail }: { label: string; value: number; tone: string; detail?: string }) {
  return (
    <StaggerItem>
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover">
        <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">
          {label} <span className="opacity-60">· 30 j</span>
        </p>
        <p className={`font-display text-[1.75rem] leading-tight tabular-nums ${tone}`}>
          {formatCAD(value)}
        </p>
        {detail && <p className="text-xs text-[var(--muted-foreground)] mt-1">{detail}</p>}
      </div>
    </StaggerItem>
  );
}

function OverviewCards({ rolling }: { rolling: RollingSummary }) {
  const expensePct = rolling.revenus > 0 ? Math.round((rolling.depenses / rolling.revenus) * 100) : 0;
  const tone = rolling.solde >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]";
  return (
    <StaggerGroup className="grid grid-cols-3 gap-4">
      <SummaryCard label="Revenus" value={rolling.revenus} tone="text-[var(--success)]" />
      <SummaryCard label="Dépenses" value={rolling.depenses} tone="text-[var(--destructive)]" detail={rolling.revenus > 0 ? `${expensePct}% des revenus` : undefined} />
      <SummaryCard label="Solde" value={rolling.solde} tone={tone} />
    </StaggerGroup>
  );
}

export function BudgetOverview({
  rolling,
  savings,
  over,
  warn,
  categoryName,
  goalInput,
  onGoalInput,
  onSave,
}: {
  rolling: RollingSummary;
  savings: SavingsGoal | null;
  over: EnvelopeStatus[];
  warn: EnvelopeStatus[];
  categoryName: (id: number) => string;
  goalInput: string;
  onGoalInput: (value: string) => void;
  onSave: () => void;
}) {
  const endMessage = rolling.solde >= 0 ? "tu épargnes sur la période" : "dépenses supérieures aux revenus";
  const window = rolling.debut
    ? `du ${formatDay(rolling.debut)} au ${formatDay(rolling.fin)}`
    : "30 derniers jours";
  return (
    <>
      <BudgetAlert over={over} warn={warn} categoryName={categoryName} />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
        <div>
          <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Solde — 30 derniers jours</p>
          <p className={`font-display text-3xl tabular-nums ${rolling.solde >= 0 ? "text-[var(--foreground)]" : "text-[var(--destructive)]"}`}>
            {formatCAD(rolling.solde)}
          </p>
        </div>
        <div className="text-right text-sm text-[var(--muted-foreground)]">
          <p className="text-xs">{window}</p>
          <p className="text-xs">{endMessage}</p>
        </div>
      </div>
      <SavingsGoalCard savings={savings} goalInput={goalInput} onGoalInput={onGoalInput} onSave={onSave} />
      <OverviewCards rolling={rolling} />
    </>
  );
}

function formatDay(iso: string) {
  return iso
    ? new Date(`${iso}T12:00:00`).toLocaleDateString("fr-CA", { day: "2-digit", month: "short" })
    : "";
}

function PeriodSelector({ periodMonths, onChange }: { periodMonths: number; onChange: (months: number) => void }) {
  return (
    <div className="flex items-center justify-end gap-1.5 text-xs">
      <span className="text-[var(--muted-foreground)]">Période :</span>
      {([['6 mois', 6], ['1 an', 12], ['2 ans', 24], ['Tout', 120]] as const).map(([label, months]) => (
        <button
          key={months}
          type="button"
          onClick={() => onChange(months)}
          className={`rounded-full px-2.5 py-1 ${periodMonths === months ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function TrendPanel({ trend, momPct }: { trend: MonthTrend[]; momPct: number | null }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
      <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
        <div className="flex items-baseline gap-2">
          <h2 className="text-sm font-semibold">Tendance mensuelle</h2>
          <TrendDelta value={momPct} />
        </div>
        <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
          <span>● Revenus</span><span>● Dépenses</span><span>━ Moy. 3 mois</span>
        </div>
      </div>
      <TrendChart data={trend} />
    </div>
  );
}

function TrendDelta({ value }: { value: number | null }) {
  if (value == null) return null;
  const color = value > 0 ? "var(--destructive)" : "var(--success)";
  return <span className="text-xs font-medium" style={{ color }}>{value > 0 ? "+" : ""}{value}% vs mois dernier</span>;
}

function ForecastPanel({
  forecast,
  revenusDeltaPct,
  depensesDeltaPct,
  onRevenusChange,
  onDepensesChange,
}: {
  forecast: CashFlowForecast | null;
  revenusDeltaPct: number;
  depensesDeltaPct: number;
  onRevenusChange: (value: number) => void;
  onDepensesChange: (value: number) => void;
}) {
  if (!forecast || forecast.points.length === 0) return null;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Prévision de trésorerie <span className="font-normal text-[var(--muted-foreground)]">· 6 prochains mois</span></h2>
        <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
          <label className="flex items-center gap-1">Revenus<input type="number" step="5" value={revenusDeltaPct} onChange={(event) => onRevenusChange(Number(event.target.value) || 0)} aria-label="Ajustement scénario revenus (%)" className="w-14 rounded border border-[var(--border)] bg-transparent px-1.5 py-0.5 text-right" />%</label>
          <label className="flex items-center gap-1">Dépenses<input type="number" step="5" value={depensesDeltaPct} onChange={(event) => onDepensesChange(Number(event.target.value) || 0)} aria-label="Ajustement scénario dépenses (%)" className="w-14 rounded border border-[var(--border)] bg-transparent px-1.5 py-0.5 text-right" />%</label>
        </div>
      </div>
      <p className="mb-3 text-xs text-[var(--muted-foreground)]">Basé sur la moyenne des 6 derniers mois : {formatCAD(forecast.moyenne_revenus)} de revenus, {formatCAD(forecast.moyenne_depenses)} de dépenses → {formatCAD(forecast.solde_mensuel_moyen)}/mois.</p>
      <div className="divide-y divide-[var(--border)]">
        {forecast.points.map((point) => (
          <div key={point.mois} className="flex items-center justify-between py-1.5 text-sm">
            <span className="text-[var(--muted-foreground)]">{point.mois}</span>
            <span className={`font-mono tabular-nums ${point.solde_mensuel >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>{point.solde_mensuel >= 0 ? "+" : ""}{formatCAD(point.solde_mensuel)}</span>
            <span className="w-28 text-right font-mono text-xs tabular-nums text-[var(--muted-foreground)]">cumul {formatCAD(point.cumul)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TagPanel({ byTag }: { byTag: TagSpend[] }) {
  const data = byTag.map((tag, index) => ({ category_id: index, nom: tag.tag, couleur: CHART_SERIES[index % CHART_SERIES.length], montant: tag.montant, pct: tag.pct }));
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
      <h2 className="text-sm font-semibold mb-3">Dépenses par tag <span className="font-normal text-[var(--muted-foreground)]">· période</span></h2>
      {data.length ? <Donut data={data} /> : <p className="text-sm text-[var(--muted-foreground)]">Aucune dépense taguée sur la période — ajoute des tags dans Transactions.</p>}
    </div>
  );
}

export function BudgetCharts({
  periodMonths,
  onPeriodChange,
  categoryShare,
  trend,
  momPct,
  forecast,
  revenusDeltaPct,
  depensesDeltaPct,
  onRevenusChange,
  onDepensesChange,
  byTag,
}: {
  periodMonths: number;
  onPeriodChange: (months: number) => void;
  categoryShare: CategoryShare;
  trend: MonthTrend[];
  momPct: number | null;
  forecast: CashFlowForecast | null;
  revenusDeltaPct: number;
  depensesDeltaPct: number;
  onRevenusChange: (value: number) => void;
  onDepensesChange: (value: number) => void;
  byTag: TagSpend[];
}) {
  return (
    <>
      <PeriodSelector periodMonths={periodMonths} onChange={onPeriodChange} />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
          <h2 className="text-sm font-semibold mb-3">Répartition des dépenses <span className="font-normal text-[var(--muted-foreground)]">· 30 j glissant</span></h2>
          <CategoryShareChart data={categoryShare} />
        </div>
        <TrendPanel trend={trend} momPct={momPct} />
      </div>
      <ForecastPanel forecast={forecast} revenusDeltaPct={revenusDeltaPct} depensesDeltaPct={depensesDeltaPct} onRevenusChange={onRevenusChange} onDepensesChange={onDepensesChange} />
      <TagPanel byTag={byTag} />
    </>
  );
}

function RecurringPanel({ recurring, projection, alerts }: { recurring: Recurring[]; projection: RecurringProjection | null; alerts: SubscriptionAlertsData | undefined }) {
  if (!hasRecurringData(recurring, alerts)) return null;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden animate-fade-in-up">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <RecurringHeader projection={projection} />
        <span className="text-sm font-mono font-semibold">{formatCAD(recurring.reduce((sum, item) => sum + item.montant_moyen, 0))}<span className="text-xs text-[var(--muted-foreground)]"> /mois</span></span>
      </div>
      <SubscriptionAlerts alerts={alerts} />
      <RecurringRows recurring={recurring} />
    </div>
  );
}

function hasRecurringData(recurring: Recurring[], alerts: SubscriptionAlertsData | undefined) {
  return recurring.length > 0 || (alerts?.nb_alertes ?? 0) > 0;
}

function RecurringHeader({ projection }: { projection: RecurringProjection | null }) {
  return <div><h2 className="text-sm font-semibold">Abonnements détectés</h2><p className="mt-0.5 text-xs text-[var(--muted-foreground)]">Dépenses mensuelles récurrentes{projection && projection.projection_annuelle_recurrents > 0 && <> · ≈ <span className="font-medium text-[var(--foreground)]">{formatCAD(projection.projection_annuelle_recurrents)}/an</span> projetés</>}</p></div>;
}

function RecurringRows({ recurring }: { recurring: Recurring[] }) {
  return <div className="divide-y divide-[var(--border)]">{recurring.map((item) => <div key={item.marchand} className="flex items-center gap-3 px-4 py-2.5"><span className="flex-1 truncate text-sm font-medium">{item.marchand}</span><span className="text-xs text-[var(--muted-foreground)]">{item.occurrences}× · dès {item.derniere_date}</span><span className="w-24 text-right font-mono text-sm tabular-nums">{formatCAD(item.montant_moyen)}</span></div>)}</div>;
}

function EnvelopePanel({ envelopes, categoryName, month }: { envelopes: EnvelopeStatus[]; categoryName: (id: number) => string; month: string }) {
  if (envelopes.length === 0) return <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up"><p className="text-sm text-[var(--muted-foreground)]">Aucune enveloppe définie pour {month}. Créez-en dans l&apos;onglet Enveloppes.</p></div>;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden animate-fade-in-up">
      <div className="px-4 py-3 border-b border-[var(--border)]"><h2 className="text-sm font-semibold">Enveloppes budgétaires</h2><p className="text-xs text-[var(--muted-foreground)] mt-0.5">{month}</p></div>
      <div className="divide-y divide-[var(--border)]">{envelopes.map((envelope, index) => <EnvelopeRow key={envelope.category_id} envelope={envelope} index={index} categoryName={categoryName} />)}</div>
    </div>
  );
}

function EnvelopeRow({ envelope, index, categoryName }: { envelope: EnvelopeStatus; index: number; categoryName: (id: number) => string }) {
  const state = envelopeState(envelope, index);
  return (
    <div className="px-4 py-3 hover:bg-[var(--muted)] transition-colors duration-150">
      <div className="flex items-center justify-between mb-1.5"><div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: state.color }} /><span className="text-sm font-medium">{categoryName(envelope.category_id)}</span></div><div className="flex items-center gap-3 text-sm"><span className={state.emphasis} style={state.textStyle}>{formatCAD(envelope.depense ?? 0)}</span><span className="text-[var(--muted-foreground)] text-xs">/ {formatCAD(envelope.budget ?? 0)}</span></div></div>
      <div className="h-1.5 rounded-full bg-[var(--muted)] overflow-hidden"><div className="h-full rounded-full bar-fill" style={{ width: `${state.pct}%`, background: state.barColor }} /></div>
    </div>
  );
}

function envelopeState(envelope: EnvelopeStatus, index: number) {
  const color = CHART_SERIES[index % CHART_SERIES.length];
  const status = envelopeStatus(envelope);
  const colors = envelopeColors(status, color);
  return {
    color,
    pct: Math.min(envelope.pct ?? 0, 100),
    ...colors,
  };
}

function envelopeStatus(envelope: EnvelopeStatus) {
  return envelope.status ?? ((envelope.pct ?? 0) > 100 ? "over" : "ok");
}

function envelopeColors(status: EnvelopeStatus["status"], color: string) {
  if (status === "over") {
    return { barColor: "var(--destructive)", emphasis: "font-medium", textStyle: { color: "var(--destructive)" } };
  }
  if (status === "warning") {
    return { barColor: "var(--warning)", emphasis: "font-medium", textStyle: { color: "var(--warning)" } };
  }
  return { barColor: color, emphasis: "text-[var(--foreground)]", textStyle: undefined };
}

export function BudgetIntegrations({
  month,
  groceryCost,
  reste,
  recurring,
  projection,
  alerts,
  envelopes,
  categoryName,
}: {
  month: string;
  groceryCost: number;
  reste: number;
  recurring: Recurring[];
  projection: RecurringProjection | null;
  alerts: SubscriptionAlertsData | undefined;
  envelopes: EnvelopeStatus[];
  categoryName: (id: number) => string;
}) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <a href="/cuisine" className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--muted)] animate-fade-in-up"><p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Courses ce mois</p><p className="font-display text-xl tabular-nums">{formatCAD(groceryCost)}</p><p className="mt-1 text-xs text-[var(--muted-foreground)]">Planifier dans Cuisine →</p></a>
        <a href="/finance" className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--muted)] animate-fade-in-up"><p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Épargne du mois (à investir)</p><p className={`font-display text-xl tabular-nums ${reste >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>{formatCAD(reste)}</p><p className="mt-1 text-xs text-[var(--muted-foreground)]">Investir dans Finance →</p></a>
      </div>
      <RecurringPanel recurring={recurring} projection={projection} alerts={alerts} />
      <EnvelopePanel envelopes={envelopes} categoryName={categoryName} month={month} />
    </>
  );
}
