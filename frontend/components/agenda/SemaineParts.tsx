'use client'

import type { Evenement } from '@/lib/agenda'
import { CATEGORIE_COLORS, couleurFor, formatHeure } from '@/lib/agenda'
import { Button } from '@/components/ui/button'

export const HOURS = Array.from({ length: 24 }, (_, i) => i)
export const DAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

const localDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

type WeekDateProps = { date: Date; index: number; today: string }

function WeekDayHeader({ date, index, today }: WeekDateProps) {
  const current = localDate(date) === today
  return <div className="bg-[var(--background)] py-2 text-center"><div className="text-xs text-[var(--muted-foreground)]">{DAY_LABELS[index]}</div><div className={current ? 'mx-auto mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--ring)] text-xs font-semibold text-white' : 'text-sm font-medium text-[var(--foreground)]'}>{date.getDate()}</div></div>
}

function WeekEvent({ event, conflict, date, hour }: { event: Evenement; conflict: boolean; date: Date; hour: number }) {
  const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const hourStart = dayStart.getTime() + hour * 3_600_000
  const hourEnd = hourStart + 3_600_000
  const eventStart = new Date(event.debut).getTime()
  const eventEnd = event.fin ? new Date(event.fin).getTime() : eventStart + 3_600_000
  const segmentStart = Math.max(hourStart, eventStart)
  const segmentEnd = Math.min(hourEnd, eventEnd)
  if (segmentEnd <= segmentStart) return null
  const startsHere = eventStart >= hourStart && eventStart < hourEnd
  const continuesFromPreviousDay = hour === 0 && eventStart < dayStart.getTime()
  const top = ((segmentStart - hourStart) / 60_000) * 0.6
  const height = Math.max(((segmentEnd - segmentStart) / 60_000) * 0.6, 3)
  return <div className={`absolute left-0 right-0 z-10 overflow-hidden px-1 text-[10px] leading-3 text-white ${eventClass(conflict)}`} style={{ top, height, backgroundColor: couleurFor(event), opacity: event.is_virtual ? 0.85 : 1 }} title={eventTitle(event, conflict)}>{(startsHere || continuesFromPreviousDay) && <span className="block truncate">{continuesFromPreviousDay ? '↳ ' : ''}{eventPrefix(conflict)}{formatHeure(event.debut)}–{event.fin ? formatHeure(event.fin) : '—'} {event.titre}</span>}</div>
}

const eventClass = (conflict: boolean) => `rounded-[var(--radius-sm)] ${conflict ? 'ring-2 ring-[var(--destructive)]' : ''}`
const eventPrefix = (conflict: boolean) => conflict ? '⚠ ' : ''
const eventTitle = (event: Evenement, conflict: boolean) => `${conflict ? '⚠ Chevauchement — ' : ''}${event.titre} ${formatHeure(event.debut)}${event.fin ? ' – ' + formatHeure(event.fin) : ''}`

function HourCell({ date, hour, eventsForDay, conflictKeys, keyOf }: { date: Date; hour: number; eventsForDay: (date: Date) => Evenement[]; conflictKeys: Set<string>; keyOf: (event: Evenement) => string }) {
  const events = eventsForDay(date)
  return <div className="relative min-h-[36px] border-t border-[var(--border)] bg-[var(--background)]">{events.map((event, index) => <WeekEvent key={`${keyOf(event)}-${index}`} event={event} date={date} hour={hour} conflict={conflictKeys.has(keyOf(event))} />)}</div>
}

function HourRow({ hour, weekDates, eventsForDay, conflictKeys, keyOf }: { hour: number; weekDates: Date[]; eventsForDay: (date: Date) => Evenement[]; conflictKeys: Set<string>; keyOf: (event: Evenement) => string }) {
  return <><div key={`h${hour}`} className="bg-[var(--background)] pr-2 pt-1 text-right text-xs text-[var(--muted-foreground)]">{hour}h</div>{weekDates.map((date, index) => <HourCell key={`${hour}-${index}`} date={date} hour={hour} eventsForDay={eventsForDay} conflictKeys={conflictKeys} keyOf={keyOf} />)}</>
}

export function WeekGrid({ weekDates, today, eventsForDay, conflictKeys, keyOf }: { weekDates: Date[]; today: string; eventsForDay: (date: Date) => Evenement[]; conflictKeys: Set<string>; keyOf: (event: Evenement) => string }) {
  return <div className="overflow-x-auto"><div className="grid gap-px overflow-hidden rounded-[var(--radius)] bg-[var(--border)]" style={{ gridTemplateColumns: '56px repeat(7, minmax(88px, 1fr))' }}><div className="bg-[var(--background)]" />{weekDates.map((date, index) => <WeekDayHeader key={index} date={date} index={index} today={today} />)}{HOURS.map((hour) => <HourRow key={hour} hour={hour} weekDates={weekDates} eventsForDay={eventsForDay} conflictKeys={conflictKeys} keyOf={keyOf} />)}</div></div>
}

export function WeekFilters({ categories, hidden, toggle }: { categories: string[]; hidden: Set<string>; toggle: (category: string) => void }) {
  if (categories.length === 0) return null
  return <div className="flex flex-wrap gap-1.5">{categories.map((category) => <CategoryButton key={category} category={category} active={!hidden.has(category)} toggle={toggle} />)}</div>
}

function CategoryButton({ category, active, toggle }: { category: string; active: boolean; toggle: (category: string) => void }) {
  const color = CATEGORIE_COLORS[category] || CATEGORIE_COLORS.autre
  return <button onClick={() => toggle(category)} aria-pressed={active} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-opacity ${active ? 'border-[var(--border)]' : 'border-transparent opacity-40'}`}><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />{category}</button>
}

export function WeekStatus({ loading, conflicts }: { loading: boolean; conflicts: number }) {
  return <>{loading && <div className="text-sm text-[var(--muted-foreground)]">Chargement…</div>}{conflicts > 0 && <div className="rounded-[var(--radius-sm)] border border-[var(--destructive)]/40 bg-[color-mix(in_srgb,var(--destructive)_8%,transparent)] px-3 py-1.5 text-xs text-[var(--destructive)]">⚠ {conflicts} événement{conflicts > 1 ? 's' : ''} en chevauchement cette semaine.</div>}</>
}

export function WeekToolbar({ weekDates, gcalReady, iCalConfigured, iCalSyncing, exportUrl, onPrev, onNext, onToday, onGoogle, onIcal }: { weekDates: Date[]; gcalReady: boolean; iCalConfigured: boolean; iCalSyncing: boolean; exportUrl: string; onPrev: () => void; onNext: () => void; onToday: () => void; onGoogle: () => void; onIcal: () => void }) {
  return <div className="flex flex-wrap items-center gap-2"><Button variant="secondary" size="sm" onClick={onPrev} aria-label="Semaine précédente">‹</Button><span className="min-w-[180px] flex-1 text-center text-sm font-medium">Semaine du {weekDates[0].toLocaleDateString('fr-CA', { day: 'numeric', month: 'long' })} au {weekDates[6].toLocaleDateString('fr-CA', { day: 'numeric', month: 'long', year: 'numeric' })}</span><Button variant="secondary" size="sm" onClick={onNext} aria-label="Semaine suivante">›</Button><Button variant="ghost" size="sm" onClick={onToday}>Aujourd&apos;hui</Button><a href={exportUrl} className="rounded-md px-2.5 py-1 text-sm text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]" title="Exporter cette semaine au format .ics">⬇ .ics</a><GoogleSyncButton ready={gcalReady} onClick={onGoogle} /><Button variant="ghost" size="sm" onClick={onIcal} disabled={!iCalConfigured || iCalSyncing} title={iCalConfigured ? 'Synchroniser automatiquement les shifts 7shifts' : 'Configure le lien 7shifts dans les Préférences'}>{iCalSyncing ? 'Sync…' : '⇄ Travail'}</Button></div>
}

function GoogleSyncButton({ ready, onClick }: { ready: boolean; onClick: () => void }) {
  return <Button variant="ghost" size="sm" onClick={onClick} title={ready ? 'Synchroniser depuis Google Calendar (OAuth)' : 'Importer un calendrier Google via son URL .ics secrète'}>⇄ Google{ready ? ' ✓' : ''}</Button>
}
