import { describe, expect, it } from "vitest";
import { msUntilNextLocalDay } from "@/lib/queries/finance";

describe("rafraîchissement de l'objectif Japon", () => {
  it("programme le prochain calcul juste après minuit local", () => {
    const now = new Date(2026, 6, 28, 23, 59, 30);

    expect(msUntilNextLocalDay(now)).toBe(35_000);
  });
});
