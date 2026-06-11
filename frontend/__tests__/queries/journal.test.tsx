import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/journal", () => ({
  journalApi: {
    entries: vi.fn().mockResolvedValue([]),
    getEntry: vi.fn().mockResolvedValue({ id: 1, date: "2026-06-10", humeur: 4, energie: 3, tags: [], note: "" }),
    putEntry: vi.fn().mockResolvedValue({ id: 1 }),
    trends: vi.fn().mockResolvedValue({ n: 0 }),
    correlations: vi.fn().mockResolvedValue({}),
  },
}));

import { journalKeys, useJournalEntry, usePutJournalEntry } from "@/lib/queries/journal";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/journal", () => {
  it("useJournalEntry charge l'entrée du jour", async () => {
    const { result } = renderHook(() => useJournalEntry("2026-06-10"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.humeur).toBe(4);
  });

  it("les clés de cache sont stables", () => {
    expect(journalKeys.entry("2026-06-10")).toEqual(["journal", "entry", "2026-06-10"]);
  });

  it("usePutJournalEntry déclenche la mutation", async () => {
    const { result } = renderHook(() => usePutJournalEntry(), { wrapper });
    result.current.mutate({ date: "2026-06-10", body: { humeur: 5, energie: 4, tags: [], note: "" } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
