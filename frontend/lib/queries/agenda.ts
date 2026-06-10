"use client";

/** Couche TanStack Query du module Agenda (#518) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTask,
  deleteTask,
  fetchEvents,
  fetchTasks,
  fetchToday,
  gcalPull,
  gcalStatus,
  markTaskDone,
  syncIcalUrl,
  type TacheCreate,
} from "@/lib/agenda";

export const agendaKeys = {
  all: ["agenda"] as const,
  today: () => [...agendaKeys.all, "today"] as const,
  events: (from?: string, to?: string) =>
    [...agendaKeys.all, "events", from ?? "", to ?? ""] as const,
  tasks: (statut?: string) => [...agendaKeys.all, "tasks", statut ?? "all"] as const,
  gcalStatus: () => [...agendaKeys.all, "gcal-status"] as const,
};

export function useAgendaToday() {
  return useQuery({ queryKey: agendaKeys.today(), queryFn: fetchToday });
}
export function useAgendaEvents(from?: string, to?: string) {
  return useQuery({ queryKey: agendaKeys.events(from, to), queryFn: () => fetchEvents(from, to) });
}
export function useAgendaTasks(statut?: string) {
  return useQuery({ queryKey: agendaKeys.tasks(statut), queryFn: () => fetchTasks(statut) });
}
export function useGcalStatus() {
  return useQuery({ queryKey: agendaKeys.gcalStatus(), queryFn: gcalStatus });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: agendaKeys.all });
}

export function useCreateTask() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (t: TacheCreate) => createTask(t), onSuccess: invalidate });
}
export function useMarkTaskDone() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => markTaskDone(id), onSuccess: invalidate });
}
export function useDeleteTask() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteTask(id), onSuccess: invalidate });
}
export function useGcalPull() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { from?: string; to?: string } | void) => gcalPull(p?.from, p?.to),
    onSuccess: invalidate,
  });
}
export function useSyncIcalUrl() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (url: string) => syncIcalUrl(url), onSuccess: invalidate });
}
