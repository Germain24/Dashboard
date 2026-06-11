import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/etudes", () => ({
  fetchCours: vi.fn().mockResolvedValue([{ id: 1, code: "IFT-1000" }]),
  fetchDeadlines: vi.fn().mockResolvedValue([]),
  fetchGpa: vi.fn().mockResolvedValue({ gpa: 3.8, detail: [] }),
  fetchSessions: vi.fn().mockResolvedValue([]),
  fetchEtudesStats: vi.fn().mockResolvedValue({}),
  fetchRevisionCards: vi.fn().mockResolvedValue([]),
  createCours: vi.fn().mockResolvedValue({ id: 2 }),
  patchCours: vi.fn().mockResolvedValue({ id: 1 }),
  deleteCours: vi.fn().mockResolvedValue(undefined),
  createEvaluation: vi.fn().mockResolvedValue({ id: 1 }),
  deleteEvaluation: vi.fn().mockResolvedValue(undefined),
  createSession: vi.fn().mockResolvedValue({ id: 1 }),
  deleteSession: vi.fn().mockResolvedValue(undefined),
  setEtudesGoal: vi.fn().mockResolvedValue({ weekly_hours: 10 }),
  addRevisionCard: vi.fn().mockResolvedValue({ id: 1 }),
  reviewRevisionCard: vi.fn().mockResolvedValue({ id: 1 }),
  deleteRevisionCard: vi.fn().mockResolvedValue(undefined),
}));

import { etudesKeys, useCours, useSetEtudesGoal } from "@/lib/queries/etudes";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/etudes", () => {
  it("useCours charge la liste des cours", async () => {
    const { result } = renderHook(() => useCours(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, code: "IFT-1000" }]);
  });

  it("les clés de cache sont stables", () => {
    expect(etudesKeys.all).toEqual(["etudes"]);
    expect(etudesKeys.gpa()).toEqual(["etudes", "gpa", "all"]);
  });

  it("useSetEtudesGoal déclenche la mutation", async () => {
    const { result } = renderHook(() => useSetEtudesGoal(), { wrapper });
    result.current.mutate(10);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
