'use client'

import { useState, useEffect, useRef } from 'react'
import { Bell } from 'lucide-react'
import { fetchNotifications, markAllRead, type Notification } from '@/lib/notifications'

export function NotificationsWidget() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const unreadCount = notifications.filter((n) => !n.read).length

  const load = async () => {
    try {
      setLoading(true)
      const data = await fetchNotifications(5)
      setNotifications(data)
    } catch {
      // silently fail — notifications are non-critical
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAllRead = async () => {
    try {
      await markAllRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    } catch {
      // silently fail
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center h-8 w-8 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors cursor-pointer"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] text-[10px] font-bold leading-none select-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-72 rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-lg z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
            <span className="text-sm font-semibold text-[var(--foreground)]">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors cursor-pointer"
              >
                Tout marquer lu
              </button>
            )}
          </div>

          {/* List */}
          <div className="divide-y divide-[var(--border)]">
            {loading && (
              <div className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
                Chargement…
              </div>
            )}
            {!loading && notifications.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
                Aucune notification
              </div>
            )}
            {!loading && notifications.map((notif) => (
              <div
                key={notif.id}
                className={`px-4 py-3 flex gap-3 items-start ${!notif.read ? 'bg-[var(--muted)]' : ''}`}
              >
                {!notif.read && (
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--primary)]" aria-label="Non lu" />
                )}
                {notif.read && <span className="mt-1.5 h-2 w-2 shrink-0" />}
                <div className="flex flex-col gap-0.5 min-w-0">
                  <p className="text-sm text-[var(--foreground)] leading-snug truncate">{notif.title}</p>
                  {notif.body && (
                    <p className="text-xs text-[var(--muted-foreground)] leading-snug line-clamp-2">{notif.body}</p>
                  )}
                  {notif.created_at && (
                    <p className="text-[11px] text-[var(--muted-foreground)]">
                      {new Date(notif.created_at).toLocaleDateString('fr-CA', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
