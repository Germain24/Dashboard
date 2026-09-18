import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/habitudes", () => ({
  fetchHabits: vi.fn().mockResolvedValue([{ id: 1, nom: "Lecture" }]),
  fetchToday: vi.fn().mockResolvedValue([]),
  fetchStreaks: vi.fn().mockResolvedValue([]),
  fetchGamification: vi.fn().mockResolvedValue([]),
  fetchStats: vi.fn().mockResolvedValue([]),
  fetchHeatmap: vi.fn().mockResolvedValue({}),
  checkEntry: vi.fn().mockResolvedValue({ id: 9 }),
  deleteEntry: vi.fn().mockResolvedValue(undefined),
  createHabit: vi.fn().mockResolvedValue({ id: 2 }),
  updateHabit: vi.fn().mockResolvedValue({ id: 1 }),
  archiveHabit: vi.fn().mockResolvedValue(undefined),
}));

import { useHabits, useCheckEntry, habitudesKeys } from "@/lib/queries/habitudes";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/habitudes", () => {
  it("useHabits charge la liste via lib/habitudes", async () => {
    const { result } = renderHook(() => useHabits(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, nom: "Lecture" }]);
  });

  it("les clés de cache sont stables et préfixées par module", () => {
    expect(habitudesKeys.all).toEqual(["habitudes"]);
    expect(habitudesKeys.habits()).toEqual(["habitudes", "habits"]);
  });

  it("useCheckEntry déclenche la mutation", async () => {
    const { result } = renderHook(() => useCheckEntry(), { wrapper });
    result.current.mutate({ habit_id: 1, date: "2026-06-10", valeur: 1 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
