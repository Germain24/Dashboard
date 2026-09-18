import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDataResults } from "@/components/CommandPaletteParts";

describe("CommandPalette data search", () => {
  afterEach(() => vi.restoreAllMocks());

  it("distinguishes an API failure from an empty result set", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 503 })));

    await expect(fetchDataResults("cours", new AbortController().signal)).rejects.toThrow(
      "Recherche temporairement indisponible.",
    );
  });

  it("returns an empty list only when the API reports no matches", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [] }), { status: 200 }),
    ));

    await expect(fetchDataResults("cours", new AbortController().signal)).resolves.toEqual([]);
  });
});
