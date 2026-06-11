import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/skincare", () => ({
  skincareApi: {
    list: vi.fn().mockResolvedValue([{ id: 1, nom: "Crème" }]),
    today: vi.fn().mockResolvedValue({ date: "2026-06-11", AM: [], PM: [], due: [] }),
    toRepurchase: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: 2 }),
    update: vi.fn().mockResolvedValue({ id: 1 }),
    remove: vi.fn().mockResolvedValue({}),
  },
}));

import { skincareKeys, useSkincareToday, useCreateSkincareProduct } from "@/lib/queries/skincare";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/skincare", () => {
  it("useSkincareToday charge la routine du jour", async () => {
    const { result } = renderHook(() => useSkincareToday(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.date).toBe("2026-06-11");
  });

  it("les clés de cache sont stables", () => {
    expect(skincareKeys.today()).toEqual(["skincare", "today"]);
  });

  it("useCreateSkincareProduct déclenche la mutation", async () => {
    const { result } = renderHook(() => useCreateSkincareProduct(), { wrapper });
    result.current.mutate({ nom: "Sérum" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
