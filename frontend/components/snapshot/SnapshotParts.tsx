"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Activity, Calendar, ChevronLeft, ChevronRight, Zap } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useActivateTemplate, useEnergyBudget, useHeatmap, useSetVacationMode, useSnapshot, useSnapshots, useTemplates, useVacationMode, useWellbeing } from "@/lib/queries/snapshot";
import type { SnapshotData } from "@/lib/snapshot";

function scoreColor(score: number): string {
  if (score >= 85) return "text-[var(--success)]";
  if (score >= 70) return "text-[var(--info)]";
  if (score >= 55) return "text-[var(--warning)]";
  return "text-[var(--destructive)]";
}

function scoreStroke(score: number): string {
  if (score >= 85) return "var(--success)";
  if (score >= 70) return "var(--info)";
  if (score >= 55) return "var(--warning)";
  return "var(--destructive)";
}

function scoreArc(score: number): number {
  return 2 * Math.PI * 28 * (1 - score / 100);
}

export function WellbeingWidget() {
  const { data, isLoading } = useWellbeing();
  if (isLoading) return <Skeleton className="h-24 rounded-xl" />;
  if (!data) return null;
  return <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"><div className="relative h-16 w-16 shrink-0"><svg width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="none" stroke="var(--accent)" strokeWidth="6" /><circle cx="32" cy="32" r="28" fill="none" stroke={scoreStroke(data.score)} strokeWidth="6" strokeLinecap="round" strokeDasharray={`${2 * Math.PI * 28}`} strokeDashoffset={scoreArc(data.score)} transform="rotate(-90 32 32)" /></svg><span className={`absolute inset-0 flex items-center justify-center text-sm font-bold ${scoreColor(data.score)}`}>{data.score}</span></div><div><p className="text-sm font-semibold">{data.label}</p><p className="mt-0.5 text-xs text-[var(--muted-foreground)]">Score bien-être du jour</p><div className="mt-1 flex gap-3">{Object.entries(data.components).map(([key, value]) => <div key={key} className="text-xs text-[var(--muted-foreground)]">{key.slice(0, 4)} <span className="font-medium text-[var(--foreground)]">{value}</span></div>)}</div></div></div>;
}

const DAYS = ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"];
const MONTHS = ["jan", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"];

export function SnapshotCard({ snap }: { snap: { date: string; data: SnapshotData } }) {
  const date = new Date(`${snap.date}T12:00:00`);
  return <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 transition-colors hover:bg-[var(--accent)]"><div className="w-10 shrink-0 text-center"><div className="text-xs text-[var(--muted-foreground)]">{DAYS[date.getDay()]}</div><div className="text-lg font-bold leading-none">{date.getDate()}</div><div className="text-xs text-[var(--muted-foreground)]">{MONTHS[date.getMonth()]}</div></div><SnapshotMetrics data={snap.data} /></div>;
}

function SnapshotMetrics({ data }: { data: SnapshotData }) {
  const items = [habitsMetric(data), budgetMetric(data), weightMetric(data), moodMetric(data), workoutMetric(data), agendaMetric(data)].filter(Boolean);
  return <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-4 gap-y-1 text-xs">{items.map((item, index) => <span key={index}>{item}</span>)}</div>;
}

function habitsMetric(data: SnapshotData) { if (!data.habitudes) return null; return <>✓ {data.habitudes.done}/{data.habitudes.total} habitudes</>; }
function budgetMetric(data: SnapshotData) { if (!data.budget || data.budget.depenses_total <= 0) return null; return <>💰 {data.budget.depenses_total.toFixed(0)} €</>; }
function weightMetric(data: SnapshotData) { if (!data.sante?.poids) return null; return <>⚖️ {data.sante.poids} kg</>; }
function moodMetric(data: SnapshotData) { if (!data.humeur) return null; return <>😊 humeur {data.humeur.valeur}/10</>; }
function workoutMetric(data: SnapshotData) { if (!data.entrainement?.nb_seances || data.entrainement.nb_seances <= 0) return null; return <>💪 {data.entrainement.nb_seances} séance(s)</>; }
function agendaMetric(data: SnapshotData) { if (!data.agenda) return null; return <>📅 {data.agenda.nb_evenements} événement(s)</>; }

export function TemplatesSection() {
  const { data: templates } = useTemplates();
  const activate = useActivateTemplate();
  if (!templates?.length) return null;
  return <div><h2 className="mb-3 text-xs font-semibold text-[var(--muted-foreground)]">Modèles de routines</h2><div className="space-y-2">{templates.map((template) => <div key={template.id} className="flex items-center gap-3 rounded-xl border border-dashed border-[var(--border)] p-3"><div className="min-w-0 flex-1"><p className="text-sm font-medium">{template.name}</p><p className="text-xs text-[var(--muted-foreground)]">{template.description}</p></div><button onClick={() => activate.mutate(template.id, { onSuccess: () => toast.success(`Routine « ${template.name} » activée`), onError: () => toast.error("Erreur activation") })} disabled={activate.isPending} className="flex shrink-0 items-center gap-1 rounded-lg bg-[var(--primary)] px-2.5 py-1.5 text-xs font-medium text-[var(--primary-foreground)] disabled:opacity-40">Activer <ChevronRight size={12} /></button></div>)}</div></div>;
}

export function VacationToggle() {
  const { data } = useVacationMode();
  const mutation = useSetVacationMode();
  const active = data?.mode_vacances ?? false;
  return <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--card)] p-3"><div><p className="text-sm font-medium">Mode vacances</p><p className="text-xs text-[var(--muted-foreground)]">Suspend les rappels habitudes & agenda</p></div><button onClick={() => mutation.mutate(!active, { onSuccess: () => toast.success(vacationMessage(active)) })} className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${vacationButtonClass(active)}`}><span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-lg transition ${vacationKnobClass(active)}`} /></button></div>;
}

function vacationMessage(active: boolean): string { return active ? "Mode vacances désactivé" : "Mode vacances activé 🏖️"; }
function vacationButtonClass(active: boolean): string { return active ? "bg-amber-500" : "bg-[var(--accent)]"; }
function vacationKnobClass(active: boolean): string { return active ? "translate-x-5" : "translate-x-0"; }

export function EnergyBudget() {
  const { data } = useEnergyBudget();
  if (!data) return null;
  const pct = data.capacite > 0 ? Math.max(0, Math.min(100, data.restant / data.capacite * 100)) : 0;
  const color = energyColor(data.statut);
  return <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4"><div className="mb-1.5 flex items-center justify-between"><h2 className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]"><Zap size={13} /> Budget d&apos;énergie du jour</h2><span className="text-sm font-semibold tabular-nums" style={{ color }}>{data.restant} / {data.capacite}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]"><div className="h-full rounded-full bar-fill" style={{ width: `${pct}%`, background: color }} /></div><p className="mt-1.5 text-xs text-[var(--muted-foreground)]">Coût prévu {data.cout_prevu} ({data.n_activites} activités)<EnergyStatus status={data.statut} /></p></div>;
}

function energyColor(status: string): string { return status === "dépassé" ? "var(--warning-foreground)" : status === "serré" ? "var(--warning)" : "var(--ring)"; }
function EnergyStatus({ status }: { status: string }) { if (status === "dépassé") return <> — journée trop chargée, allège.</>; if (status === "serré") return <> — peu de marge.</>; return null; }

export function TimeMachine() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const { data: snap, isLoading } = useSnapshot(date);
  const shift = (days: number) => { const next = new Date(`${date}T12:00:00`); next.setDate(next.getDate() + days); const iso = next.toISOString().slice(0, 10); if (iso <= today) setDate(iso); };
  return <div><h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]"><Calendar size={13} /> Time machine — rejoue une journée passée</h2><div className="mb-2 flex items-center gap-2"><button onClick={() => shift(-1)} aria-label="Jour précédent" className="rounded-lg border border-[var(--border)] p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><ChevronLeft size={15} /></button><input type="date" value={date} max={today} onChange={(event) => setDate(event.target.value)} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" /><button onClick={() => shift(1)} disabled={date >= today} aria-label="Jour suivant" className="rounded-lg border border-[var(--border)] p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)] disabled:opacity-40"><ChevronRight size={15} /></button></div><TimeMachineResult isLoading={isLoading} snap={snap} /></div>;
}

function TimeMachineResult({ isLoading, snap }: { isLoading: boolean; snap: { date: string; data: SnapshotData } | undefined }) { if (isLoading) return <Skeleton className="h-16 rounded-xl" />; if (snap) return <SnapshotCard snap={snap} />; return <p className="text-sm text-[var(--muted-foreground)]">Aucune donnée pour cette date.</p>; }

export function AnnualHeatmap() {
  const [metric, setMetric] = useState("Humeur");
  const { data } = useHeatmap(metric);
  const byDate = heatmapDataCells(data);
  const today = new Date();
  const end = endOfWeek(today);
  const weeks = buildWeeks(end);
  const { min, max } = heatmapDataBounds(data);
  return <div><HeatmapHeader metric={metric} available={heatmapDataOptions(data, metric)} onChange={setMetric} /><div className="overflow-x-auto no-scrollbar"><HeatmapGrid weeks={weeks} today={today} byDate={byDate} min={min} max={max} /></div></div>;
}

function heatmapCells(cells: { date: string; value: number }[] | undefined): Map<string, number> { return new Map((cells ?? []).map((cell) => [cell.date, cell.value])); }
function heatmapBounds(min: number | undefined, max: number | undefined): { min: number; max: number } { return { min: min ?? 0, max: max ?? 0 }; }
function heatmapOptions(options: string[] | undefined, metric: string): string[] { return options ?? [metric]; }
type HeatmapData = { cells?: { date: string; value: number }[]; min?: number; max?: number; available?: string[] };
function heatmapDataCells(data: HeatmapData | undefined): Map<string, number> { return heatmapCells(data?.cells); }
function heatmapDataBounds(data: HeatmapData | undefined): { min: number; max: number } { return heatmapBounds(data?.min, data?.max); }
function heatmapDataOptions(data: HeatmapData | undefined, metric: string): string[] { return heatmapOptions(data?.available, metric); }

function HeatmapHeader({ metric, available, onChange }: { metric: string; available: string[]; onChange: (value: string) => void }) { return <div className="mb-2 flex items-center justify-between"><h2 className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]"><Activity size={13} /> Heatmap annuelle</h2><select value={metric} onChange={(event) => onChange(event.target.value)} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">{available.map((item) => <option key={item} value={item}>{item}</option>)}</select></div>; }
function HeatmapGrid({ weeks, today, byDate, min, max }: { weeks: Date[][]; today: Date; byDate: Map<string, number>; min: number; max: number }) { return <div className="flex gap-[3px]">{weeks.map((week, index) => <div key={index} className="flex flex-col gap-[3px]">{week.map((day) => <HeatCell key={day.toISOString()} day={day} today={today} byDate={byDate} min={min} max={max} />)}</div>)}</div>; }

function endOfWeek(date: Date): Date { const end = new Date(date); end.setDate(end.getDate() + (7 - ((end.getDay() + 6) % 7)) - 1); return end; }
function buildWeeks(end: Date): Date[][] { const start = new Date(end); start.setDate(start.getDate() - 53 * 7 + 1); const weeks: Date[][] = []; const cursor = new Date(start); while (cursor <= end) { const week: Date[] = []; for (let index = 0; index < 7; index += 1) { week.push(new Date(cursor)); cursor.setDate(cursor.getDate() + 1); } weeks.push(week); } return weeks; }
function heatLevel(day: Date, byDate: Map<string, number>, min: number, max: number): number { const iso = day.toISOString().slice(0, 10); if (!byDate.has(iso)) return 0; if (max === min) return 3; return 1 + Math.min(3, Math.floor(((byDate.get(iso)! - min) / (max - min)) * 4)); }
function HeatCell({ day, today, byDate, min, max }: { day: Date; today: Date; byDate: Map<string, number>; min: number; max: number }) { const iso = day.toISOString().slice(0, 10); const level = heatLevel(day, byDate, min, max); const background = day > today ? "transparent" : level === 0 ? "var(--muted)" : `color-mix(in srgb, var(--ring) ${level * 25}%, transparent)`; return <div title={`${iso}${byDate.has(iso) ? ` : ${byDate.get(iso)}` : ""}`} className="h-2.5 w-2.5 rounded-[2px]" style={{ background }} />; }

export function SnapshotContent() {
  const [days, setDays] = useState(14);
  const { data: snapshots, isLoading } = useSnapshots(days);
  return <div className="space-y-6"><WellbeingWidget /><EnergyBudget /><TimeMachine /><VacationToggle /><TemplatesSection /><HistorySection days={days} setDays={setDays} snapshots={snapshots} isLoading={isLoading} /><AnnualHeatmap /></div>;
}

function HistorySection({ days, setDays, snapshots, isLoading }: { days: number; setDays: (days: number) => void; snapshots: { date: string; data: SnapshotData }[] | undefined; isLoading: boolean }) {
  return <div><div className="mb-3 flex items-center justify-between"><h2 className="text-xs font-semibold text-[var(--muted-foreground)]">Historique</h2><div className="flex gap-1">{[7, 14, 30].map((value) => <button key={value} onClick={() => setDays(value)} className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${days === value ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--accent)] text-[var(--muted-foreground)]"}`}>{value}j</button>)}</div></div><HistoryResults snapshots={snapshots} isLoading={isLoading} /></div>;
}

function HistoryResults({ snapshots, isLoading }: { snapshots: { date: string; data: SnapshotData }[] | undefined; isLoading: boolean }) { if (isLoading) return <div className="space-y-2">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16 rounded-xl" />)}</div>; if (!snapshots?.length) return <div className="py-8 text-center text-[var(--muted-foreground)]"><Activity size={28} className="mx-auto mb-2 opacity-30" /><p className="text-sm">Aucun snapshot disponible</p><p className="mt-1 text-xs">Les snapshots sont générés automatiquement chaque soir à 23h55.</p></div>; return <div className="space-y-2">{snapshots.map((snap) => <SnapshotCard key={snap.date} snap={snap} />)}</div>; }
