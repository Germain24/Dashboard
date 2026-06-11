import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/jobs", () => ({
  fetchJobs: vi.fn().mockResolvedValue([{ job_id: "backup_db" }]),
  fetchRuns: vi.fn().mockResolvedValue([]),
  forceRun: vi.fn().mockResolvedValue({ status: "triggered" }),
  pauseJob: vi.fn().mockResolvedValue({ status: "paused" }),
  resumeJob: vi.fn().mockResolvedValue({ status: "resumed" }),
}));
vi.mock("@/lib/notifications", () => ({
  fetchNotifications: vi.fn().mockResolvedValue([]),
  fetchPrefs: vi.fn().mockResolvedValue([]),
  markRead: vi.fn().mockResolvedValue({ ok: true }),
  markAllRead: vi.fn().mockResolvedValue({ marked: 0 }),
  clearAll: vi.fn().mockResolvedValue({ deleted: 0 }),
  setPref: vi.fn().mockResolvedValue({ ok: true }),
}));

import { jobsKeys, useJobs, useForceRun } from "@/lib/queries/jobs";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/jobs", () => {
  it("useJobs charge la liste des jobs", async () => {
    const { result } = renderHook(() => useJobs(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ job_id: "backup_db" }]);
  });

  it("les clés de cache sont stables", () => {
    expect(jobsKeys.runs("x")).toEqual(["jobs", "runs", "x"]);
  });

  it("useForceRun déclenche la mutation", async () => {
    const { result } = renderHook(() => useForceRun(), { wrapper });
    result.current.mutate("backup_db");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
