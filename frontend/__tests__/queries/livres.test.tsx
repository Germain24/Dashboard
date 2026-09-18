import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/livres", () => ({
  fetchBooks: vi.fn().mockResolvedValue([{ id: 1, titre: "Dune" }]),
  searchBooks: vi.fn().mockResolvedValue([]),
  fetchAnnualStats: vi.fn().mockResolvedValue({ livres_lus: 3 }),
  fetchRecommendations: vi.fn().mockResolvedValue([]),
  fetchReadingGoal: vi.fn().mockResolvedValue({ annual_goal: 12 }),
  fetchEstimate: vi.fn().mockResolvedValue({}),
  fetchNotes: vi.fn().mockResolvedValue([]),
  fetchQuotes: vi.fn().mockResolvedValue([]),
  createBook: vi.fn().mockResolvedValue({ id: 2 }),
  updateBook: vi.fn().mockResolvedValue({ id: 1 }),
  deleteBook: vi.fn().mockResolvedValue(undefined),
  setReadingGoal: vi.fn().mockResolvedValue({ annual_goal: 20 }),
  createNote: vi.fn().mockResolvedValue({ id: 1 }),
  deleteNote: vi.fn().mockResolvedValue(undefined),
  createQuote: vi.fn().mockResolvedValue({ id: 1 }),
  deleteQuote: vi.fn().mockResolvedValue(undefined),
  createReadingSession: vi.fn().mockResolvedValue({ id: 1 }),
}));

import { livresKeys, useBooks, useSetReadingGoal } from "@/lib/queries/livres";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/livres", () => {
  it("useBooks charge la bibliothèque", async () => {
    const { result } = renderHook(() => useBooks(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, titre: "Dune" }]);
  });

  it("les clés de cache sont stables", () => {
    expect(livresKeys.notes(3)).toEqual(["livres", "notes", 3]);
  });

  it("useSetReadingGoal déclenche la mutation", async () => {
    const { result } = renderHook(() => useSetReadingGoal(), { wrapper });
    result.current.mutate(20);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
