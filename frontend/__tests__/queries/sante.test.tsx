import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/sante", () => ({
  santeApi: {
    listMesures: vi.fn().mockResolvedValue([{ id: 1, date: "2026-06-10", poids: 75 }]),
    getGoal: vi.fn().mockResolvedValue({ id: 1 }),
    getPlanToday: vi.fn().mockResolvedValue({ date: "2026-06-10" }),
    getProjection: vi.fn().mockResolvedValue({}),
    waterToday: vi.fn().mockResolvedValue({ eau_ml: 0 }),
    sleepSummary: vi.fn().mockResolvedValue({}),
    workoutBurn: vi.fn().mockResolvedValue({}),
    weeklyQuality: vi.fn().mockResolvedValue({}),
    energyBalance: vi.fn().mockResolvedValue({}),
    listAliments: vi.fn().mockResolvedValue([]),
    listFavorites: vi.fn().mockResolvedValue([]),
    listPhotos: vi.fn().mockResolvedValue([]),
    upsertMesure: vi.fn().mockResolvedValue({ id: 1 }),
    updateGoal: vi.fn().mockResolvedValue({ id: 1 }),
    generatePlan: vi.fn().mockResolvedValue({ date: "2026-06-10" }),
    patchPlan: vi.fn().mockResolvedValue({ date: "2026-06-10" }),
    addWater: vi.fn().mockResolvedValue({ eau_ml: 250 }),
    logSleep: vi.fn().mockResolvedValue({}),
    addFavorite: vi.fn().mockResolvedValue({ favorites: [] }),
    removeFavorite: vi.fn().mockResolvedValue({ favorites: [] }),
    uploadPhoto: vi.fn().mockResolvedValue({ id: 1 }),
  },
}));

import { santeKeys, useMesures, useAddWater } from "@/lib/queries/sante";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/sante", () => {
  it("useMesures charge les mesures", async () => {
    const { result } = renderHook(() => useMesures(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, date: "2026-06-10", poids: 75 }]);
  });

  it("les clés de cache sont stables", () => {
    expect(santeKeys.mesures(180)).toEqual(["sante", "mesures", 180]);
  });

  it("useAddWater déclenche la mutation", async () => {
    const { result } = renderHook(() => useAddWater(), { wrapper });
    result.current.mutate(250);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
