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
  fetchIcalSource,
  saveIcalSource,
  removeIcalSource,
  replanWeeklyRevisions,
  syncIcalSource,
  syncIcalUrl,
  type IcalSourceStatus,
  type TacheCreate,
} from "@/lib/agenda";

export const agendaKeys = {
  all: ["agenda"] as const,
  today: () => [...agendaKeys.all, "today"] as const,
  events: (from?: string, to?: string) =>
    [...agendaKeys.all, "events", from ?? "", to ?? ""] as const,
  tasks: (statut?: string) => [...agendaKeys.all, "tasks", statut ?? "all"] as const,
  gcalStatus: () => [...agendaKeys.all, "gcal-status"] as const,
  icalSource: () => [...agendaKeys.all, "ical-source"] as const,
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
export function useIcalSource() {
  return useQuery({ queryKey: agendaKeys.icalSource(), queryFn: fetchIcalSource });
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

export function useSaveIcalSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ url, label }: { url: string; label?: string }) => saveIcalSource(url, label),
    onSuccess: (status: IcalSourceStatus) => {
      qc.setQueryData(agendaKeys.icalSource(), status);
      void qc.invalidateQueries({ queryKey: agendaKeys.all });
    },
  });
}

export function useRemoveIcalSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: removeIcalSource,
    onSuccess: (status) => {
      qc.setQueryData(agendaKeys.icalSource(), status);
      void qc.invalidateQueries({ queryKey: agendaKeys.all });
    },
  });
}

export function useSyncIcalSource() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: syncIcalSource, onSuccess: invalidate, onSettled: invalidate });
}

export function useReplanWeeklyRevisions() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: replanWeeklyRevisions, onSuccess: invalidate });
}
