import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchSummary } from "@/lib/budget";

describe("budget API errors", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("surfaces server errors instead of accepting an error body as budget data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Budget indisponible" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(fetchSummary("2026-09")).rejects.toThrow("API 503 Budget indisponible");
  });
});
