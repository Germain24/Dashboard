import { describe, expect, it } from "vitest";
import { capitalBreakIndexes } from "@/lib/finance-chart";

describe("capitalBreakIndexes", () => {
  it("ignore les apports ordinaires", () => {
    expect(
      capitalBreakIndexes([{ investit: 10_000 }, { investit: 10_500 }, { investit: 12_000 }]),
    ).toEqual([]);
  });

  it("repère une disparition puis une restauration majeure du périmètre", () => {
    expect(
      capitalBreakIndexes([
        { investit: 15_000 },
        { investit: 1_057 },
        { investit: 1_057 },
        { investit: 16_057 },
      ]),
    ).toEqual([1, 3]);
  });
});
