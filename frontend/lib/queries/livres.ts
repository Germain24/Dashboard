"use client";

/** Couche TanStack Query du module Livres (#528). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createBook,
  createNote,
  createQuote,
  createReadingSession,
  deleteBook,
  deleteNote,
  deleteQuote,
  fetchAnnualStats,
  fetchBooks,
  fetchEstimate,
  fetchNotes,
  fetchQuotes,
  fetchReadingGoal,
  fetchRecommendations,
  searchBooks,
  setReadingGoal,
  updateBook,
  type Book,
} from "@/lib/livres";

export const livresKeys = {
  all: ["livres"] as const,
  books: (opts?: { statut?: string; sort?: string }) =>
    [...livresKeys.all, "books", opts ?? {}] as const,
  search: (q: string) => [...livresKeys.all, "search", q] as const,
  annualStats: (year?: number) => [...livresKeys.all, "annual-stats", year ?? "current"] as const,
  recommendations: () => [...livresKeys.all, "recommendations"] as const,
  readingGoal: () => [...livresKeys.all, "reading-goal"] as const,
  estimate: (id: number) => [...livresKeys.all, "estimate", id] as const,
  notes: (id: number) => [...livresKeys.all, "notes", id] as const,
  quotes: (id: number) => [...livresKeys.all, "quotes", id] as const,
};

export function useBooks(opts?: { statut?: string; sort?: string }) {
  return useQuery({ queryKey: livresKeys.books(opts), queryFn: () => fetchBooks(opts) });
}
export function useBookSearch(q: string) {
  return useQuery({
    queryKey: livresKeys.search(q),
    queryFn: () => searchBooks(q),
    enabled: q.trim().length > 1,
  });
}
export function useAnnualStats(year?: number) {
  return useQuery({ queryKey: livresKeys.annualStats(year), queryFn: () => fetchAnnualStats(year) });
}
export function useLivresRecommendations() {
  return useQuery({ queryKey: livresKeys.recommendations(), queryFn: fetchRecommendations });
}
export function useReadingGoal() {
  return useQuery({ queryKey: livresKeys.readingGoal(), queryFn: fetchReadingGoal });
}
export function useBookEstimate(id: number | null) {
  return useQuery({
    queryKey: livresKeys.estimate(id ?? 0),
    queryFn: () => fetchEstimate(id as number),
    enabled: id != null,
  });
}
export function useBookNotes(id: number | null) {
  return useQuery({
    queryKey: livresKeys.notes(id ?? 0),
    queryFn: () => fetchNotes(id as number),
    enabled: id != null,
  });
}
export function useBookQuotes(id: number | null) {
  return useQuery({
    queryKey: livresKeys.quotes(id ?? 0),
    queryFn: () => fetchQuotes(id as number),
    enabled: id != null,
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: livresKeys.all });
}

export function useCreateBook() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (d: Partial<Book>) => createBook(d), onSuccess: invalidate });
}
export function useUpdateBook() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Book> }) => updateBook(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteBook() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteBook(id), onSuccess: invalidate });
}
export function useSetReadingGoal() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (goal: number) => setReadingGoal(goal), onSuccess: invalidate });
}
export function useCreateBookNote() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; contenu: string; page: number | null }) =>
      createNote(p.id, p.contenu, p.page),
    onSuccess: invalidate,
  });
}
export function useDeleteBookNote() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteNote(id), onSuccess: invalidate });
}
export function useCreateBookQuote() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; texte: string; page: number | null }) =>
      createQuote(p.id, p.texte, p.page),
    onSuccess: invalidate,
  });
}
export function useDeleteBookQuote() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteQuote(id), onSuccess: invalidate });
}
export function useCreateReadingSession() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: Parameters<typeof createReadingSession>) => createReadingSession(...p),
    onSuccess: invalidate,
  });
}
