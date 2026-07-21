"use client";

/** Couche TanStack Query du module Études (#523) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addRevisionCard,
  addSkillPreuve,
  createCours,
  createEvaluation,
  createSession,
  createSkill,
  deleteCours,
  deleteEvaluation,
  deleteRevisionCard,
  deleteSession,
  deleteSkill,
  fetchCours,
  fetchDeadlines,
  fetchEtudesStats,
  fetchGpa,
  fetchRevisionCards,
  fetchSessions,
  fetchSkills,
  fetchSkillsStats,
  patchCours,
  patchSkill,
  reviewRevisionCard,
  setEtudesGoal,
  type Cours,
  type CoursCreate,
  type EvaluationCreate,
  type Skill,
} from "@/lib/etudes";

export const etudesKeys = {
  all: ["etudes"] as const,
  cours: (params?: { semestre?: string; actif?: boolean }) =>
    [...etudesKeys.all, "cours", params ?? {}] as const,
  deadlines: (days: number) => [...etudesKeys.all, "deadlines", days] as const,
  gpa: (semestre?: string) => [...etudesKeys.all, "gpa", semestre ?? "all"] as const,
  sessions: (coursId?: number) => [...etudesKeys.all, "sessions", coursId ?? "all"] as const,
  stats: (days: number) => [...etudesKeys.all, "stats", days] as const,
  revisionCards: (dueOnly: boolean) => [...etudesKeys.all, "revision-cards", dueOnly] as const,
  skills: () => [...etudesKeys.all, "skills"] as const,
  skillsStats: () => [...etudesKeys.all, "skills-stats"] as const,
};

export function useCours(params?: { semestre?: string; actif?: boolean }) {
  return useQuery({ queryKey: etudesKeys.cours(params), queryFn: () => fetchCours(params) });
}
export function useDeadlines(days = 30) {
  return useQuery({ queryKey: etudesKeys.deadlines(days), queryFn: () => fetchDeadlines(days) });
}
export function useGpa(semestre?: string) {
  return useQuery({ queryKey: etudesKeys.gpa(semestre), queryFn: () => fetchGpa(semestre) });
}
export function useEtudesSessions(coursId?: number) {
  return useQuery({ queryKey: etudesKeys.sessions(coursId), queryFn: () => fetchSessions(coursId) });
}
export function useEtudesStats(days = 120) {
  return useQuery({ queryKey: etudesKeys.stats(days), queryFn: () => fetchEtudesStats(days) });
}
export function useRevisionCards(dueOnly = false) {
  return useQuery({
    queryKey: etudesKeys.revisionCards(dueOnly),
    queryFn: () => fetchRevisionCards(dueOnly),
  });
}
export function useSkills() {
  return useQuery({ queryKey: etudesKeys.skills(), queryFn: () => fetchSkills() });
}
export function useSkillsStats() {
  return useQuery({ queryKey: etudesKeys.skillsStats(), queryFn: () => fetchSkillsStats() });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: etudesKeys.all });
}

export function useCreateCours() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: CoursCreate) => createCours(d), onSuccess: invalidate });
}
export function usePatchCours() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Cours> }) => patchCours(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteCours() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteCours(id), onSuccess: invalidate });
}
export function useCreateEvaluation() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: EvaluationCreate) => createEvaluation(d), onSuccess: invalidate });
}
export function useDeleteEvaluation() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteEvaluation(id), onSuccess: invalidate });
}
export function useCreateEtudesSession() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (d: { cours_id?: number; duree_min: number; sujet?: string; note?: string }) =>
      createSession(d),
    onSuccess: invalidate,
  });
}
export function useDeleteEtudesSession() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteSession(id), onSuccess: invalidate });
}
export function useSetEtudesGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (h: number) => setEtudesGoal(h), onSuccess: invalidate });
}
export function useAddRevisionCard() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { recto: string; verso: string; coursId?: number }) =>
      addRevisionCard(p.recto, p.verso, p.coursId),
    onSuccess: invalidate,
  });
}
export function useReviewRevisionCard() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; quality: number }) => reviewRevisionCard(p.id, p.quality),
    onSuccess: invalidate,
  });
}
export function useDeleteRevisionCard() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteRevisionCard(id), onSuccess: invalidate });
}
export function useCreateSkill() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (d: { nom: string; categorie: string; niveau?: number }) => createSkill(d),
    onSuccess: invalidate,
  });
}
export function useUpdateSkill() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Pick<Skill, "nom" | "categorie" | "niveau">> }) =>
      patchSkill(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteSkill() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteSkill(id), onSuccess: invalidate });
}
export function useAddPreuve() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; texte: string; date?: string }) => addSkillPreuve(p.id, p.texte, p.date),
    onSuccess: invalidate,
  });
}
