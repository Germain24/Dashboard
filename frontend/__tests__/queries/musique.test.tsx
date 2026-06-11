import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/musique", () => ({
  musiqueApi: {
    tracks: vi.fn().mockResolvedValue([{ id: 1, title: "Song" }]),
    ambiances: vi.fn().mockResolvedValue([]),
    playlist: vi.fn().mockResolvedValue([]),
    reco: vi.fn().mockResolvedValue([]),
    discovery: vi.fn().mockResolvedValue({ ambiance: "calme", suggestions: [] }),
    scan: vi.fn().mockResolvedValue({ ajoutes: 1, majs: 0, total: 1 }),
    classify: vi.fn().mockResolvedValue({ message: "ok" }),
    resetClassify: vi.fn().mockResolvedValue({ reinitialises: 0 }),
    addAmbiance: vi.fn().mockResolvedValue(undefined),
    removeAmbiance: vi.fn().mockResolvedValue(undefined),
  },
}));

import { musiqueKeys, useTracks, useScanLibrary } from "@/lib/queries/musique";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/musique", () => {
  it("useTracks charge les pistes", async () => {
    const { result } = renderHook(() => useTracks(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, title: "Song" }]);
  });

  it("les clés de cache intègrent la recherche", () => {
    expect(musiqueKeys.tracks("lofi", "calme")).toEqual(["musique", "tracks", "lofi", "calme"]);
  });

  it("useScanLibrary déclenche la mutation", async () => {
    const { result } = renderHook(() => useScanLibrary(), { wrapper });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total).toBe(1);
  });
});
