import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/entrainement", () => ({
  entrainementApi: {
    getToday: vi.fn().mockResolvedValue({ date: "2026-06-10", jour_label: "Push", slots: [] }),
    getProgram: vi.fn().mockResolvedValue({ id: 1, jours: [] }),
    listExercices: vi.fn().mockResolvedValue([]),
    listSessions: vi.fn().mockResolvedValue([]),
    getSession: vi.fn().mockResolvedValue({ id: 1, sets: [] }),
    getIntensityToday: vi.fn().mockResolvedValue({ date: "2026-06-10", intensity: "high" }),
    listCardio: vi.fn().mockResolvedValue([]),
    getProgression: vi.fn().mockResolvedValue({ points: [] }),
    getMuscleVolume: vi.fn().mockResolvedValue([]),
    getCorrelation: vi.fn().mockResolvedValue({ weeks: [], correlation: null, n: 0 }),
    createSession: vi.fn().mockResolvedValue({ id: 2, sets: [] }),
    patchSession: vi.fn().mockResolvedValue({ id: 2, sets: [] }),
    addSet: vi.fn().mockResolvedValue({ id: 3 }),
    startMesocycle: vi.fn().mockResolvedValue({ active: true }),
    stopMesocycle: vi.fn().mockResolvedValue({ active: false }),
    createCardio: vi.fn().mockResolvedValue({ id: 1 }),
    deleteCardio: vi.fn().mockResolvedValue(undefined),
    patchProgramJour: vi.fn().mockResolvedValue({ id: 1 }),
  },
}));

import { entrainementKeys, useEntrainementToday, useAddSet } from "@/lib/queries/entrainement";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/entrainement", () => {
  it("useEntrainementToday charge la vue du jour", async () => {
    const { result } = renderHook(() => useEntrainementToday(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.jour_label).toBe("Push");
  });

  it("les clés de cache sont stables", () => {
    expect(entrainementKeys.all).toEqual(["entrainement"]);
    expect(entrainementKeys.session(4)).toEqual(["entrainement", "session", 4]);
  });

  it("useAddSet déclenche la mutation", async () => {
    const { result } = renderHook(() => useAddSet(), { wrapper });
    result.current.mutate({ seanceId: 1, set: { exercice_id: 2, reps: 8, poids_kg: 60, rpe: null } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
