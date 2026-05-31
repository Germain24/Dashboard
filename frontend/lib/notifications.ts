import { api } from './api'

export type Notification = {
  id: string
  title: string
  body?: string
  read: boolean
  created_at?: string
}

export async function fetchNotifications(limit = 10): Promise<Notification[]> {
  return api<Notification[]>(`/api/notifications?limit=${limit}`)
}

export async function markAllRead(): Promise<void> {
  await api<void>('/api/notifications/read-all', { method: 'POST' })
}
