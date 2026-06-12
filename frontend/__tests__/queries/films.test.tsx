import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/films", () => ({
  fetchWatchlist: vi.fn().mockResolvedValue([
    { id: 1, titre: "Inception", type: "film", statut: "vu" },
  ]),
  fetchWatchStats: vi.fn().mockResolvedValue({
    films_total: 3,
    series_total: 2,
    films_vus: 2,
    series_vues: 1,
    vus_annee: 3,
    temps_estime_heures: 8.5,
    annee: 2026,
  }),
  searchTmdb: vi.fn().mockResolvedValue([]),
  fetchProgress: vi.fn().mockResolvedValue({}),
  createWatchItem: vi.fn().mockResolvedValue({ id: 2 }),
  updateWatchItem: vi.fn().mockResolvedValue({ id: 1 }),
  deleteWatchItem: vi.fn().mockResolvedValue(undefined),
  updateProgress: vi.fn().mockResolvedValue({ saison: 1, episode_courant: 3 }),
  parseGenres: vi.fn().mockReturnValue([]),
}));

import {
  filmsKeys,
  useWatchlist,
  useWatchStats,
  useAddWatchItem,
} from "@/lib/queries/films";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/films", () => {
  it("useWatchlist charge la liste", async () => {
    const { result } = renderHook(() => useWatchlist(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].titre).toBe("Inception");
  });

  it("useWatchStats charge les statistiques", async () => {
    const { result } = renderHook(() => useWatchStats(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.films_total).toBe(3);
    expect(result.current.data?.temps_estime_heures).toBe(8.5);
  });

  it("les clés de cache sont stables et préfixées", () => {
    expect(filmsKeys.all).toEqual(["films-series"]);
    expect(filmsKeys.watchlist()).toEqual(["films-series", "watchlist", {}]);
    expect(filmsKeys.stats()).toEqual(["films-series", "stats"]);
  });

  it("useAddWatchItem déclenche la mutation", async () => {
    const { result } = renderHook(() => useAddWatchItem(), { wrapper });
    result.current.mutate({ titre: "Avatar", type: "film" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
