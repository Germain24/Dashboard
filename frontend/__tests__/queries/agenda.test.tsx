import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/agenda", () => ({
  fetchToday: vi.fn().mockResolvedValue({ date: "2026-06-10", evenements: [], slots_libres: [], taches_urgentes: [] }),
  fetchEvents: vi.fn().mockResolvedValue([{ id: 1, titre: "Cours" }]),
  fetchTasks: vi.fn().mockResolvedValue([]),
  gcalStatus: vi.fn().mockResolvedValue({ configured: false, calendar_id: "" }),
  gcalPull: vi.fn().mockResolvedValue({ created_events: 0, skipped_duplicates: 0 }),
  syncIcalUrl: vi.fn().mockResolvedValue({ created_events: 2, skipped_duplicates: 0, created_rules: 0 }),
  createTask: vi.fn().mockResolvedValue({ id: 5 }),
  markTaskDone: vi.fn().mockResolvedValue({ id: 5, statut: "done" }),
  deleteTask: vi.fn().mockResolvedValue(undefined),
}));

import { agendaKeys, useAgendaEvents, useCreateTask } from "@/lib/queries/agenda";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/agenda", () => {
  it("useAgendaEvents charge la fenêtre via lib/agenda", async () => {
    const { result } = renderHook(() => useAgendaEvents("2026-06-08", "2026-06-14"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, titre: "Cours" }]);
  });

  it("les clés de cache intègrent la fenêtre", () => {
    expect(agendaKeys.all).toEqual(["agenda"]);
    expect(agendaKeys.events("a", "b")).toEqual(["agenda", "events", "a", "b"]);
  });

  it("useCreateTask déclenche la mutation", async () => {
    const { result } = renderHook(() => useCreateTask(), { wrapper });
    result.current.mutate({ titre: "Test" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
