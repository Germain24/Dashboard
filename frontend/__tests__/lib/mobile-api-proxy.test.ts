import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { exportIcsUrl } from "@/lib/agenda";
import { MEDIA_BASE } from "@/lib/musique";
import { mediaUrl } from "@/lib/sante";

describe("same-origin backend proxy", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends versioned API calls through the frontend proxy", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api("/health");

    expect(fetchMock).toHaveBeenCalledWith(
      "/proxy/api/v1/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("builds media and export links on the same origin", () => {
    expect(MEDIA_BASE).toBe("/proxy/media/music");
    expect(mediaUrl("/media/sante/photo.jpg")).toBe("/proxy/media/sante/photo.jpg");
    expect(exportIcsUrl("2026-09-01", "2026-09-30")).toBe(
      "/proxy/agenda/export-ical?from=2026-09-01&to=2026-09-30",
    );
  });
});
