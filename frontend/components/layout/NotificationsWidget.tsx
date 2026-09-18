"use client";

import { useState, useEffect, useId, useRef, useSyncExternalStore } from "react";
import { Bell, Settings2, Trash2, BellRing } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Notification, NotifPref } from "@/lib/notifications";
import {
  useClearNotifications,
  useMarkAllRead,
  useMarkRead,
  useNotifPrefs,
  useNotifications,
  useSetNotifPref,
} from "@/lib/queries/jobs";

type PushPermission = NotificationPermission | "unsupported";

function subscribeToPushPermission(onChange: () => void): () => void {
  window.addEventListener("mc:notification-permission", onChange);
  return () => window.removeEventListener("mc:notification-permission", onChange);
}

function getPushPermission(): PushPermission {
  return "Notification" in window ? window.Notification.permission : "unsupported";
}

function getServerPushPermission(): PushPermission {
  return "default";
}

export function NotificationsWidget() {
  const [open, setOpen] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const pushPermission = useSyncExternalStore(
    subscribeToPushPermission,
    getPushPermission,
    getServerPushPermission,
  );
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const lastSeenId = useRef<number | null>(null);
  const popoverId = useId();

  const notificationsQ = useNotifications(15);
  const notifications: Notification[] = notificationsQ.data ?? [];
  const prefsQ = useNotifPrefs();
  const prefs: NotifPref[] = prefsQ.isError ? [] : (prefsQ.data ?? []);
  const markReadMutation = useMarkRead();
  const markAllReadMutation = useMarkAllRead();
  const clearMutation = useClearNotifications();
  const setPrefMutation = useSetNotifPref();

  const unreadCount = notifications.filter((n) => !n.lu).length;

  // Notifications navigateur sur les nouveautés (pas de spam au 1er chargement).
  useEffect(() => {
    if (!notificationsQ.data) return;
    const items = notificationsQ.data;
    const prev = lastSeenId.current;
    lastSeenId.current = items.reduce((m, n) => Math.max(m, n.id), prev ?? 0);
    if (prev == null) return;
    if (typeof window === "undefined" || !("Notification" in window)) return;
    if (window.Notification.permission !== "granted") return;
    for (const n of items) {
      if (n.id > prev && !n.lu) {
        try {
          new window.Notification(n.titre, { body: n.message || undefined });
        } catch {
          /* noop */
        }
      }
    }
  }, [notificationsQ.data]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setShowPrefs(false);
        setConfirmClear(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      setShowPrefs(false);
      setConfirmClear(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const openPrefs = () => setShowPrefs((v) => !v);

  const togglePref = (source: string, enabled: boolean) => {
    setPrefMutation.mutate({ source, enabled });
  };

  const onClickNotif = (n: Notification) => {
    if (n.lu) return;
    markReadMutation.mutate(n.id);
  };

  const handleMarkAllRead = () => markAllReadMutation.mutate();

  const requestPush = async () => {
    if (!("Notification" in window) || pushPermission === "denied") return;
    await window.Notification.requestPermission();
    window.dispatchEvent(new Event("mc:notification-permission"));
  };

  const pushGranted = pushPermission === "granted";
  const pushDenied = pushPermission === "denied";

  return (
    <div ref={ref} className="relative">
      <button
        ref={triggerRef}
        type="button"
        data-ui-control
        onClick={() => {
          setOpen((v) => !v);
          setConfirmClear(false);
        }}
        className="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
        aria-label={unreadCount ? `Notifications, ${unreadCount} non lues` : "Notifications"}
        aria-expanded={open}
        aria-controls={popoverId}
        aria-haspopup="dialog"
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span
            aria-hidden="true"
            className="absolute top-0.5 right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] text-[10px] font-bold leading-none select-none"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={popoverId}
            role="dialog"
            aria-label="Centre de notifications"
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            className="glass-modal fixed left-3 right-3 top-16 z-50 w-auto rounded-lg md:absolute md:bottom-full md:left-0 md:right-auto md:top-auto md:mb-2 md:w-80"
          >
            <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-[var(--border)]">
              <span className="text-sm font-semibold text-[var(--foreground)]">Notifications</span>
              <div className="flex items-center gap-1">
                {pushPermission !== "unsupported" && !pushGranted && (
                  <button
                    type="button"
                    data-ui-control
                    onClick={() => void requestPush()}
                    disabled={pushDenied}
                    title={pushDenied ? "Notifications bloquées dans les réglages du navigateur" : "Activer les notifications navigateur"}
                    aria-label={pushDenied ? "Notifications navigateur bloquées" : "Activer les notifications navigateur"}
                    className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
                  >
                    <BellRing className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                )}
                <button
                  type="button"
                  data-ui-control
                  onClick={() => void openPrefs()}
                  title="Préférences"
                  aria-label="Préférences"
                  className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
                >
                  <Settings2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  data-ui-control
                  onClick={() => setConfirmClear(true)}
                  disabled={notifications.length === 0 || clearMutation.isPending}
                  title="Tout effacer"
                  aria-label="Tout effacer"
                  className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)] hover:bg-[var(--muted)]"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
            </div>

            {confirmClear && (
              <div
                role="group"
                aria-label="Confirmation de suppression des notifications"
                className="border-b border-[var(--border)] bg-[var(--destructive-muted)] px-4 py-3"
              >
                <p className="text-sm font-medium text-[var(--foreground)]">Effacer toutes les notifications ?</p>
                <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">Cette action est définitive.</p>
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setConfirmClear(false)}
                    className="rounded px-2.5 py-1 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={() => clearMutation.mutate(undefined, { onSuccess: () => setConfirmClear(false) })}
                    disabled={clearMutation.isPending}
                    className="rounded bg-[var(--destructive)] px-2.5 py-1 text-xs font-medium text-[var(--destructive-foreground)] disabled:opacity-50"
                  >
                    {clearMutation.isPending ? "Suppression…" : "Effacer"}
                  </button>
                </div>
              </div>
            )}

            {clearMutation.isError && (
              <p role="alert" className="px-4 py-2 text-xs text-[var(--destructive)]">
                Impossible d&apos;effacer les notifications. Réessaie.
              </p>
            )}
            {markAllReadMutation.isError && (
              <p role="alert" className="px-4 py-2 text-xs text-[var(--destructive)]">
                Impossible de mettre les notifications à jour.
              </p>
            )}
            {markReadMutation.isError && (
              <p role="alert" className="px-4 py-2 text-xs text-[var(--destructive)]">
                Impossible de marquer cette notification comme lue.
              </p>
            )}

            {showPrefs && (
              <div className="border-b border-[var(--border)] px-4 py-2.5">
                <p className="mb-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                  Sources activées
                </p>
                {prefsQ.isPending && (
                  <p role="status" className="text-xs text-[var(--muted-foreground)]">Chargement des préférences…</p>
                )}
                {prefsQ.isError && (
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <p className="text-[var(--destructive)]">Impossible de charger les préférences.</p>
                    <button type="button" onClick={() => void prefsQ.refetch()} className="underline underline-offset-2">Réessayer</button>
                  </div>
                )}
                {!prefsQ.isPending && !prefsQ.isError && prefs.length === 0 && (
                  <p className="text-xs text-[var(--muted-foreground)]">Aucune source.</p>
                )}
                <div className="space-y-1">
                  {prefs.map((p) => (
                    <label
                      key={p.source}
                      className="flex items-center justify-between gap-2 text-sm"
                    >
                      <span className="truncate">{p.source}</span>
                      <input
                        type="checkbox"
                        checked={p.enabled}
                        onChange={(e) => void togglePref(p.source, e.target.checked)}
                      />
                    </label>
                  ))}
                </div>
              </div>
            )}

            {unreadCount > 0 && !notificationsQ.isError && (
              <div className="px-4 py-1.5 border-b border-[var(--border)]">
                <button
                  type="button"
                  onClick={() => void handleMarkAllRead()}
                  disabled={markAllReadMutation.isPending}
                  aria-busy={markAllReadMutation.isPending}
                  className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors cursor-pointer"
                >
                  {markAllReadMutation.isPending ? "Mise à jour…" : "Tout marquer lu"}
                </button>
              </div>
            )}

            {notificationsQ.isError && (
              <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3" role="alert">
                <p className="text-sm text-[var(--destructive)]">Impossible de charger les notifications.</p>
                <button
                  type="button"
                  onClick={() => void notificationsQ.refetch()}
                  disabled={notificationsQ.isFetching}
                  className="shrink-0 text-xs underline underline-offset-2 disabled:opacity-50"
                >
                  Réessayer
                </button>
              </div>
            )}

            <div className="max-h-80 divide-y divide-[var(--border)] overflow-y-auto" aria-busy={notificationsQ.isFetching}>
              {notificationsQ.isPending && (
                <div role="status" className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
                  Chargement des notifications…
                </div>
              )}
              {!notificationsQ.isPending && !notificationsQ.isError && notifications.length === 0 && (
                <div className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
                  Aucune notification
                </div>
              )}
              {notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => void onClickNotif(n)}
                  className={`flex w-full gap-3 items-start px-4 py-3 text-left hover:bg-[var(--muted)] ${!n.lu ? "bg-[var(--muted)]" : ""}`}
                >
                  <span
                    className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${!n.lu ? "bg-[var(--primary)]" : "bg-transparent"}`}
                  />
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <p className="text-sm text-[var(--foreground)] leading-snug">{n.titre}</p>
                    {n.message && (
                      <p className="text-xs text-[var(--muted-foreground)] leading-snug line-clamp-2">
                        {n.message}
                      </p>
                    )}
                    {n.created_at && (
                      <p className="text-[11px] text-[var(--muted-foreground)]">
                        {new Date(n.created_at).toLocaleString("fr-CA", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
