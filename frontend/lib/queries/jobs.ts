"use client";

/** Couche TanStack Query des modules Jobs (scheduler) + Notifications (#526). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJobs, fetchRuns, forceRun, pauseJob, resumeJob } from "@/lib/jobs";
import {
  clearAll,
  fetchNotifications,
  fetchPrefs,
  markAllRead,
  markRead,
  setPref,
} from "@/lib/notifications";

export const jobsKeys = {
  all: ["jobs"] as const,
  list: () => [...jobsKeys.all, "list"] as const,
  runs: (jobId: string) => [...jobsKeys.all, "runs", jobId] as const,
};

export const notificationsKeys = {
  all: ["notifications"] as const,
  list: (limit: number) => [...notificationsKeys.all, "list", limit] as const,
  prefs: () => [...notificationsKeys.all, "prefs"] as const,
};

export function useJobs() {
  return useQuery({ queryKey: jobsKeys.list(), queryFn: fetchJobs });
}
export function useJobRuns(jobId: string | null) {
  return useQuery({
    queryKey: jobsKeys.runs(jobId ?? ""),
    queryFn: () => fetchRuns(jobId as string),
    enabled: jobId != null,
  });
}
export function useNotifications(limit = 10) {
  return useQuery({
    queryKey: notificationsKeys.list(limit),
    queryFn: () => fetchNotifications(limit),
  });
}
export function useNotifPrefs() {
  return useQuery({ queryKey: notificationsKeys.prefs(), queryFn: fetchPrefs });
}

function useInvalidateJobs() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: jobsKeys.all });
}
function useInvalidateNotifications() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: notificationsKeys.all });
}

export function useForceRun() {
  const invalidate = useInvalidateJobs();
  return useMutation({ mutationFn: (jobId: string) => forceRun(jobId), onSuccess: invalidate });
}
export function usePauseJob() {
  const invalidate = useInvalidateJobs();
  return useMutation({ mutationFn: (jobId: string) => pauseJob(jobId), onSuccess: invalidate });
}
export function useResumeJob() {
  const invalidate = useInvalidateJobs();
  return useMutation({ mutationFn: (jobId: string) => resumeJob(jobId), onSuccess: invalidate });
}
export function useMarkRead() {
  const invalidate = useInvalidateNotifications();
  return useMutation({ mutationFn: (id: number) => markRead(id), onSuccess: invalidate });
}
export function useMarkAllRead() {
  const invalidate = useInvalidateNotifications();
  return useMutation({ mutationFn: () => markAllRead(), onSuccess: invalidate });
}
export function useClearNotifications() {
  const invalidate = useInvalidateNotifications();
  return useMutation({ mutationFn: () => clearAll(), onSuccess: invalidate });
}
export function useSetNotifPref() {
  const invalidate = useInvalidateNotifications();
  return useMutation({
    mutationFn: (p: { source: string; enabled: boolean }) => setPref(p.source, p.enabled),
    onSuccess: invalidate,
  });
}
