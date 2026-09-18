import type { BuffettProgress } from "@/lib/finance";
import type { OptProgress } from "./buffett-ui";

export type BuffettProgressFlags = {
  interrupted: boolean;
  paused: boolean;
  resumeAt: string | null;
};

function isInterrupted(progress: BuffettProgress | null) {
  if (!progress) return false;
  if (progress.statut === "interrompu") return true;
  return progress.statut === "en_cours" && progress.active === false;
}

function pausedUntil(progress: BuffettProgress | null) {
  return progress?.paused_until;
}

export function progressFlags(progress: BuffettProgress | null): BuffettProgressFlags {
  const until = pausedUntil(progress);
  return {
    interrupted: isInterrupted(progress),
    paused: until != null,
    resumeAt: formatResumeAt(until),
  };
}

export function scoreHistory(optProgress: OptProgress | null) {
  return optProgress?.score_history;
}

export function optimizationIsActive(
  progress: BuffettProgress | null,
  optProgress: OptProgress | null,
) {
  return Boolean(progress?.active || optProgress?.active);
}

function formatResumeAt(pausedUntil: number | null | undefined) {
  if (pausedUntil == null) return null;
  return new Date(pausedUntil * 1000).toLocaleTimeString("fr-CA", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
