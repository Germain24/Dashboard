'use client'

import { useState, useEffect, useRef } from 'react'
import { Bell, Settings2, Trash2, BellRing } from 'lucide-react'
import type { Notification, NotifPref } from '@/lib/notifications'
import {
  useClearNotifications, useMarkAllRead, useMarkRead,
  useNotifPrefs, useNotifications, useSetNotifPref,
} from '@/lib/queries/jobs'

const POLL_MS = 30_000

export function NotificationsWidget() {
  const [open, setOpen] = useState(false)
  const [showPrefs, setShowPrefs] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const lastSeenId = useRef<number | null>(null)

  const notificationsQ = useNotifications(15)
  const notifications: Notification[] = notificationsQ.data ?? []
  const prefsQ = useNotifPrefs()
  const prefs: NotifPref[] = prefsQ.isError ? [] : prefsQ.data ?? []
  const markReadMutation = useMarkRead()
  const markAllReadMutation = useMarkAllRead()
  const clearMutation = useClearNotifications()
  const setPrefMutation = useSetNotifPref()

  // Poll : TanStack refait la requête, on garde la cadence historique.
  useEffect(() => {
    const t = setInterval(() => void notificationsQ.refetch(), POLL_MS)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const unreadCount = notifications.filter((n) => !n.lu).length

  // Notifications navigateur sur les nouveautés (pas de spam au 1er chargement).
  useEffect(() => {
    if (!notificationsQ.data) return
    const items = notificationsQ.data
    const prev = lastSeenId.current
    lastSeenId.current = items.reduce((m, n) => Math.max(m, n.id), prev ?? 0)
    if (prev == null) return
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (window.Notification.permission !== 'granted') return
    for (const n of items) {
      if (n.id > prev && !n.lu) {
        try { new window.Notification(n.titre, { body: n.message || undefined }) } catch { /* noop */ }
      }
    }
  }, [notificationsQ.data])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setShowPrefs(false) }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const openPrefs = () => setShowPrefs((v) => !v)

  const togglePref = (source: string, enabled: boolean) => {
    setPrefMutation.mutate({ source, enabled })
  }

  const onClickNotif = (n: Notification) => {
    if (n.lu) return
    markReadMutation.mutate(n.id)
  }

  const handleMarkAllRead = () => markAllReadMutation.mutate()

  const handleClear = () => clearMutation.mutate()

  const requestPush = async () => {
    if (!('Notification' in window)) return
    await window.Notification.requestPermission()
  }

  const pushGranted = typeof window !== 'undefined' && 'Notification' in window && window.Notification.permission === 'granted'

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center h-8 w-8 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors cursor-pointer"
        aria-label="Notifications">
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] text-[10px] font-bold leading-none select-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-80 rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-lg z-50">
          <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-[var(--border)]">
            <span className="text-sm font-semibold text-[var(--foreground)]">Notifications</span>
            <div className="flex items-center gap-1">
              {!pushGranted && (
                <button onClick={() => void requestPush()} title="Activer les notifications navigateur"
                  className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]">
                  <BellRing className="h-3.5 w-3.5" />
                </button>
              )}
              <button onClick={() => void openPrefs()} title="Préférences" aria-label="Préférences"
                className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]">
                <Settings2 className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => void handleClear()} title="Tout effacer" aria-label="Tout effacer"
                className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)] hover:bg-[var(--muted)]">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {showPrefs && (
            <div className="border-b border-[var(--border)] px-4 py-2.5">
              <p className="mb-1.5 text-xs font-medium text-[var(--muted-foreground)]">Sources activées</p>
              {prefs.length === 0 && <p className="text-xs text-[var(--muted-foreground)]">Aucune source.</p>}
              <div className="space-y-1">
                {prefs.map((p) => (
                  <label key={p.source} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate">{p.source}</span>
                    <input type="checkbox" checked={p.enabled}
                      onChange={(e) => void togglePref(p.source, e.target.checked)} />
                  </label>
                ))}
              </div>
            </div>
          )}

          {unreadCount > 0 && (
            <div className="px-4 py-1.5 border-b border-[var(--border)]">
              <button onClick={() => void handleMarkAllRead()}
                className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors cursor-pointer">
                Tout marquer lu
              </button>
            </div>
          )}

          <div className="max-h-80 divide-y divide-[var(--border)] overflow-y-auto">
            {notifications.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">Aucune notification</div>
            )}
            {notifications.map((n) => (
              <button key={n.id} onClick={() => void onClickNotif(n)}
                className={`flex w-full gap-3 items-start px-4 py-3 text-left hover:bg-[var(--muted)] ${!n.lu ? 'bg-[var(--muted)]' : ''}`}>
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${!n.lu ? 'bg-[var(--primary)]' : 'bg-transparent'}`} />
                <div className="flex min-w-0 flex-col gap-0.5">
                  <p className="text-sm text-[var(--foreground)] leading-snug">{n.titre}</p>
                  {n.message && <p className="text-xs text-[var(--muted-foreground)] leading-snug line-clamp-2">{n.message}</p>}
                  {n.created_at && (
                    <p className="text-[11px] text-[var(--muted-foreground)]">
                      {new Date(n.created_at).toLocaleString('fr-CA', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
