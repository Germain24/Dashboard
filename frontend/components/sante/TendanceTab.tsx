'use client'

import { useMemo } from 'react'
import type { MesureSante, NutritionGoal, ProjectionResponse } from '@/lib/sante'
import { INK } from '@/lib/design/colors'

type Props = { mesures: MesureSante[]; projection: ProjectionResponse | null; goal: NutritionGoal | null }
type Point = { date: Date; weight: number }
type Bounds = { xMin: number; xMax: number; yMin: number; yMax: number }
type ChartModel = { points: Point[]; smooth: Point[]; path: string; smoothPath: string; bounds: Bounds; trendLine: TrendLine | null; goalLine: number | null }
type TrendLine = { x1: number; y1: number; x2: number; y2: number }

const WIDTH = 720
const HEIGHT = 220
const PAD = { top: 10, right: 20, bottom: 30, left: 40 }

function weightPoints(mesures: MesureSante[]): Point[] {
  return mesures.filter((measure) => measure.poids !== null && measure.poids !== undefined).map((measure) => ({ date: new Date(measure.date), weight: measure.poids as number }))
}

function chartBounds(points: Point[]): Bounds {
  const xs = points.map((point) => point.date.getTime())
  const ys = points.map((point) => point.weight)
  return { xMin: Math.min(...xs), xMax: Math.max(...xs), yMin: Math.floor(Math.min(...ys) - 1), yMax: Math.ceil(Math.max(...ys) + 1) }
}

function xScale(time: number, bounds: Bounds): number {
  if (bounds.xMax === bounds.xMin) return PAD.left
  return PAD.left + ((time - bounds.xMin) / (bounds.xMax - bounds.xMin)) * (WIDTH - PAD.left - PAD.right)
}

function yScale(weight: number, bounds: Bounds): number {
  return HEIGHT - PAD.bottom - ((weight - bounds.yMin) / (bounds.yMax - bounds.yMin)) * (HEIGHT - PAD.top - PAD.bottom)
}

function pathOf(points: Point[], bounds: Bounds): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${xScale(point.date.getTime(), bounds).toFixed(1)} ${yScale(point.weight, bounds).toFixed(1)}`).join(' ')
}

function movingAverage(points: Point[]): Point[] {
  return points.map((point, index) => {
    const window = points.slice(Math.max(0, index - 6), index + 1)
    return { date: point.date, weight: window.reduce((sum, item) => sum + item.weight, 0) / window.length }
  })
}

function makeTrendLine(projection: ProjectionResponse | null, points: Point[], bounds: Bounds): TrendLine | null {
  const trend = projection?.trend_30d
  if (!trend || points.length < 2) return null
  const last = points[points.length - 1]
  const slope = trend.slope_kg_per_day
  const startDate = new Date(last.date.getTime() - 30 * 86400000)
  const futureDate = targetDate(projection, last)
  return { x1: xScale(startDate.getTime(), bounds), y1: yScale(last.weight - slope * 30, bounds), x2: xScale(Math.min(futureDate.getTime(), bounds.xMax + 60 * 86400000), bounds), y2: yScale(projection.target_weight, bounds) }
}

function targetDate(projection: ProjectionResponse, last: Point): Date {
  return projection.target_date ? new Date(projection.target_date) : new Date(last.date.getTime() + 60 * 86400000)
}

function makeModel(points: Point[], projection: ProjectionResponse | null, goal: NutritionGoal | null): ChartModel {
  const visible = points.slice(-90)
  const bounds = chartBounds(visible)
  const smooth = movingAverage(visible)
  return { points: visible, smooth, bounds, path: pathOf(visible, bounds), smoothPath: pathOf(smooth, bounds), trendLine: makeTrendLine(projection, visible, bounds), goalLine: goal?.poids_cible ? yScale(goal.poids_cible, bounds) : null }
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return <div className="rounded border border-[var(--border)] p-3"><div className="text-xs text-[var(--muted-foreground)]">{label}</div><div className="text-lg font-semibold">{value}</div>{hint && <div className="mt-0.5 text-xs text-[var(--muted-foreground)]">{hint}</div>}</div>
}

function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)} kg/sem`
}

function TrendStat({ label, trend }: { label: string; trend?: { slope_kg_per_week: number; samples: number } | null }) {
  return <StatCard label={label} value={trend ? signed(trend.slope_kg_per_week) : '—'} hint={trend ? `${trend.samples} pts` : 'pas assez de données'} />
}

function TrendStats({ points, projection, goal }: { points: Point[]; projection: ProjectionResponse | null; goal: NutritionGoal | null }) {
  return <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><CurrentWeightCard points={points} /><TrendStat label="Tendance 7j" trend={projection?.trend_7d} /><TrendStat label="Tendance 30j" trend={projection?.trend_30d} /><GoalCard goal={goal} projection={projection} /></div>
}

function CurrentWeightCard({ points }: { points: Point[] }) {
  const current = points[points.length - 1]
  return <StatCard label="Poids actuel" value={`${current.weight.toFixed(1)} kg`} hint={`${points.length} mesures`} />
}

function GoalCard({ goal, projection }: { goal: NutritionGoal | null; projection: ProjectionResponse | null }) {
  return <StatCard label="Objectif" value={goalValue(goal)} hint={projectionHint(projection)} />
}

const goalValue = (goal: NutritionGoal | null) => goal?.poids_cible ? `${goal.poids_cible.toFixed(1)} kg` : 'non défini'

function projectionHint(projection: ProjectionResponse | null): string {
  if (!projection) return ''
  if (projection.target_date) return `≈ ${projection.target_date}`
  return projection.note || ''
}

function ProjectionNote({ projection }: { projection: ProjectionResponse | null }) {
  if (!projection) return null
  const style = projection.confidence === 'high' ? 'border-[var(--success)]/40 bg-[var(--success)]/10' : projection.confidence === 'medium' ? 'border-[var(--ring)]/40 bg-[var(--ring)]/10' : 'border-[var(--warning)]/40 bg-[var(--warning)]/10'
  return <div className={`rounded border px-3 py-2 text-sm ${style}`}>{projection.note}</div>
}

function OptionalLine({ line, goal }: { line: TrendLine | null; goal: boolean }) {
  if (!line) return null
  return goal ? <GoalLine line={line} /> : <TrendLineSvg line={line} />
}

function GoalLine({ line }: { line: TrendLine }) {
  return <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke="var(--success)" strokeDasharray="4 4" opacity={0.7} />
}

function TrendLineSvg({ line }: { line: TrendLine }) {
  return <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke={INK.slate} strokeDasharray="6 4" strokeWidth={1.5} opacity={0.6} />
}

function ChartSvg({ model }: { model: ChartModel }) {
  const { bounds } = model
  const levels = [bounds.yMin, Math.round((bounds.yMin + bounds.yMax) / 2), bounds.yMax]
  return <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-auto w-full"><ChartLevels levels={levels} bounds={bounds} /><OptionalLine line={model.goalLine === null ? null : { x1: PAD.left, y1: model.goalLine, x2: WIDTH - PAD.right, y2: model.goalLine }} goal /><OptionalLine line={model.trendLine} goal={false} /><path d={model.path} fill="none" stroke="currentColor" strokeWidth={1.5} opacity={0.45} /><path d={model.smoothPath} fill="none" stroke="var(--ring)" strokeWidth={2} />{model.points.map((point, index) => <circle key={index} cx={xScale(point.date.getTime(), bounds)} cy={yScale(point.weight, bounds)} r={2} fill="currentColor" />)}</svg>
}

function ChartLevels({ levels, bounds }: { levels: number[]; bounds: Bounds }) {
  return <>{levels.map((level) => <g key={level}><line x1={PAD.left} y1={yScale(level, bounds)} x2={WIDTH - PAD.right} y2={yScale(level, bounds)} stroke="currentColor" strokeOpacity={0.1} /><text x={PAD.left - 4} y={yScale(level, bounds) + 4} fontSize="10" textAnchor="end" fill="currentColor" opacity={0.5}>{level}</text></g>)}</>
}

function ChartPanel({ model }: { model: ChartModel }) {
  return <div className="overflow-x-auto rounded border border-[var(--border)] p-3"><ChartSvg model={model} /><div className="mt-1 text-xs text-[var(--muted-foreground)]">90 derniers jours · ligne bleue = <strong>moyenne mobile 7j</strong> · gris pâle = mesures brutes · pointillé vert = objectif</div></div>
}

function EmptyTrend() {
  return <div className="rounded border border-[var(--border)] p-4 text-sm text-[var(--muted-foreground)]">Aucune mesure de poids — saisis-en une dans l’onglet Composition.</div>
}

export function TendanceTab({ mesures, projection, goal }: Props) {
  const points = useMemo(() => weightPoints(mesures), [mesures])
  if (points.length === 0) return <EmptyTrend />
  const model = makeModel(points, projection, goal)
  return <div className="space-y-4"><TrendStats points={model.points} projection={projection} goal={goal} /><ProjectionNote projection={projection} /><ChartPanel model={model} /></div>
}
