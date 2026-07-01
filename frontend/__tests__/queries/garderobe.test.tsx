import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/garderobe", () => ({
  garderobeApi: {
    listVetements: vi.fn().mockResolvedValue([{ id: "v1", nom: "Jean" }]),
    getMeteo: vi.fn().mockResolvedValue({ temp: 20 }),
    getSlots: vi.fn().mockResolvedValue({ slots: [] }),
    stats: vi.fn().mockResolvedValue({ total: 1 }),
    history: vi.fn().mockResolvedValue([]),
    recommendations: vi.fn().mockResolvedValue({ total_tenues: 0, conseils: [] }),
    frequence: vi.fn().mockResolvedValue({}),
    getPlanner: vi.fn().mockResolvedValue({ days: [] }),
    suggest: vi.fn().mockResolvedValue({ slots: [], use_body: false }),
    valider: vi.fn().mockResolvedValue({ history_id: 1, updates: [] }),
    updateVetement: vi.fn().mockResolvedValue({ id: "v1" }),
    uploadPhoto: vi.fn().mockResolvedValue({ id: "v1" }),
    setPlannerDay: vi.fn().mockResolvedValue({ date: "2026-06-10", tenue: {} }),
    getObjectif: vi.fn().mockResolvedValue({
      total_emplacements: 2,
      total_remplis: 1,
      types: [{ nom: "T-shirts", ordre: 0, quantite_objectif: 2, echelle: [], rempli: 1, emplacements: [], excedent: [] }],
    }),
    syncObjectif: vi.fn().mockResolvedValue({ types: 55 }),
  },
}));

import { garderobeKeys, useObjectif, useVetements, useValiderTenue } from "@/lib/queries/garderobe";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/garderobe", () => {
  it("useVetements charge la garde-robe", async () => {
    const { result } = renderHook(() => useVetements(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: "v1", nom: "Jean" }]);
  });

  it("les clés de cache sont stables", () => {
    expect(garderobeKeys.all).toEqual(["garderobe"]);
    expect(garderobeKeys.history(20)).toEqual(["garderobe", "history", 20]);
  });

  it("useValiderTenue déclenche la mutation", async () => {
    const { result } = renderHook(() => useValiderTenue(), { wrapper });
    result.current.mutate({ tenue: { Haut: "v1" }, use_body: false });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("useObjectif charge l'objectif", async () => {
    const { result } = renderHook(() => useObjectif(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_emplacements).toBe(2);
    expect(garderobeKeys.objectif()).toEqual(["garderobe", "objectif"]);
  });
});
