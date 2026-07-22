import { describe, expect, it } from "vitest";
import {
  annualizedCapitalReturn,
  capitalBreakIndexes,
  moneyWeightedAnnualizedReturn,
} from "@/lib/finance-chart";

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

describe("annualizedCapitalReturn", () => {
  it("annualise un gain de 75,83 % sur environ six ans autour de 9,86 %", () => {
    const result = annualizedCapitalReturn(17_583, 10_000, "2020-07-22", "2026-07-22");
    expect(result).not.toBeNull();
    expect(result!).toBeGreaterThan(9.8);
    expect(result!).toBeLessThan(9.9);
  });

  it("refuse une durée ou un capital nul", () => {
    expect(annualizedCapitalReturn(100, 0, "2020-01-01", "2026-01-01")).toBeNull();
    expect(annualizedCapitalReturn(100, 100, "2026-01-01", "2026-01-01")).toBeNull();
  });
});

describe("moneyWeightedAnnualizedReturn", () => {
  it("retrouve environ 10 % sans apport intermédiaire", () => {
    const history = [
      { date: "2025-01-01", valeur: 1_000, investit: 1_000 },
      { date: "2026-01-01", valeur: 1_100, investit: 1_000 },
    ];

    const result = moneyWeightedAnnualizedReturn(history, history);

    expect(result).not.toBeNull();
    expect(result!).toBeGreaterThan(9.9);
    expect(result!).toBeLessThan(10.1);
  });

  it("neutralise un apport effectué à mi-période", () => {
    const history = [
      { date: "2025-01-01", valeur: 1_000, investit: 1_000 },
      { date: "2025-07-02", valeur: 2_048.81, investit: 2_000 },
      { date: "2026-01-01", valeur: 2_148.81, investit: 2_000 },
    ];

    const result = moneyWeightedAnnualizedReturn(history, history);

    expect(result).not.toBeNull();
    expect(result!).toBeGreaterThan(9.9);
    expect(result!).toBeLessThan(10.1);
  });

  it("applique les mêmes apports à une série CW8", () => {
    const history = [
      { date: "2023-01-01", valeur: 100, investit: 100 },
      { date: "2024-01-01", valeur: 160, investit: 150 },
      { date: "2025-01-01", valeur: 220, investit: 150 },
    ];
    const cw8 = history.map(({ date, valeur }) => ({ date, valeur }));

    expect(moneyWeightedAnnualizedReturn(cw8, history)).toBeCloseTo(
      moneyWeightedAnnualizedReturn(history, history)!,
      10,
    );
  });

  it("laisse le capital constant quand un relevé intermédiaire manque", () => {
    const values = [
      { date: "2025-01-01", valeur: 1_000 },
      { date: "2026-01-01", valeur: 1_100 },
    ];
    const capital = [{ date: "2025-01-01", investit: 1_000 }];

    expect(moneyWeightedAnnualizedReturn(values, capital)).toBeCloseTo(10, 1);
  });

  it("refuse les séries sans durée ou sans flux des deux signes", () => {
    expect(
      moneyWeightedAnnualizedReturn(
        [{ date: "2026-01-01", valeur: 100 }],
        [{ date: "2026-01-01", investit: 100 }],
      ),
    ).toBeNull();
    expect(
      moneyWeightedAnnualizedReturn(
        [
          { date: "2025-01-01", valeur: 100 },
          { date: "2026-01-01", valeur: 0 },
        ],
        [{ date: "2025-01-01", investit: 100 }],
      ),
    ).toBeNull();
  });
});
