import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/data", () => ({
  fetchTables: vi.fn().mockResolvedValue(["habit", "book"]),
  importBackup: vi.fn().mockResolvedValue({ total_inserted: 3, skipped_tables: [], tables: {} }),
  seedDemo: vi.fn().mockResolvedValue({ seeded: { habit: 2 } }),
}));

import { donneesKeys, useTables, useImportBackup } from "@/lib/queries/donnees";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/donnees", () => {
  it("useTables charge la liste des tables", async () => {
    const { result } = renderHook(() => useTables(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(["habit", "book"]);
  });

  it("les clés de cache sont préfixées", () => {
    expect(donneesKeys.tables()).toEqual(["donnees", "tables"]);
  });

  it("useImportBackup déclenche la mutation", async () => {
    const { result } = renderHook(() => useImportBackup(), { wrapper });
    result.current.mutate({ data: {}, mode: "merge" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_inserted).toBe(3);
  });
});
