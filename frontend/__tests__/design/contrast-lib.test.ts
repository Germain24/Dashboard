import { describe, it, expect } from "vitest";
import { parseCssColor, composite, contrastRatio } from "@/lib/design/contrast";

describe("parseCssColor", () => {
  it("parse hex 6", () => {
    expect(parseCssColor("#04142c")).toEqual({ r: 4, g: 20, b: 44, a: 1 });
  });
  it("parse hex 3", () => {
    expect(parseCssColor("#fff")).toEqual({ r: 255, g: 255, b: 255, a: 1 });
  });
  it("parse rgb moderne avec alpha", () => {
    expect(parseCssColor("rgb(255 255 255 / 0.72)")).toEqual({ r: 255, g: 255, b: 255, a: 0.72 });
  });
  it("parse rgb moderne sans alpha", () => {
    expect(parseCssColor("rgb(4 20 44)")).toEqual({ r: 4, g: 20, b: 44, a: 1 });
  });
  it("parse transparent", () => {
    expect(parseCssColor("transparent")).toEqual({ r: 0, g: 0, b: 0, a: 0 });
  });
  it("rejette l'invalide", () => {
    expect(parseCssColor("var(--foo)")).toBeNull();
  });
});

describe("composite", () => {
  it("alpha 1 = premier plan", () => {
    const fg = { r: 10, g: 20, b: 30, a: 1 };
    expect(composite(fg, { r: 255, g: 255, b: 255, a: 1 })).toEqual({ ...fg, a: 1 });
  });
  it("alpha 0.5 = moyenne", () => {
    const out = composite({ r: 0, g: 0, b: 0, a: 0.5 }, { r: 255, g: 255, b: 255, a: 1 });
    expect(out.r).toBeCloseTo(127.5, 0);
    expect(out.a).toBe(1);
  });
});

describe("contrastRatio", () => {
  it("noir sur blanc = 21", () => {
    const black = { r: 0, g: 0, b: 0, a: 1 };
    const white = { r: 255, g: 255, b: 255, a: 1 };
    expect(contrastRatio(black, white)).toBeCloseTo(21, 1);
  });
  it("symétrique", () => {
    const a = { r: 4, g: 20, b: 44, a: 1 };
    const b = { r: 250, g: 249, b: 245, a: 1 };
    expect(contrastRatio(a, b)).toBeCloseTo(contrastRatio(b, a), 6);
  });
  it("encre sur papier crème > 15", () => {
    // --foreground #1b1c1a sur --background #faf9f5
    const ink = { r: 27, g: 28, b: 26, a: 1 };
    const paper = { r: 250, g: 249, b: 245, a: 1 };
    expect(contrastRatio(ink, paper)).toBeGreaterThan(15);
  });
});
