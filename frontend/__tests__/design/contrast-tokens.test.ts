/**
 * Contraste AA des tokens Verre Clair (les deux thèmes).
 * Le CSS est parsé depuis globals.css : le design system est testé
 * à la source, pas via un rendu.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { parseCssColor, composite, contrastRatio, type Rgba } from "@/lib/design/contrast";

const css = fs.readFileSync(
  path.resolve(__dirname, "../../src/app/globals.css"),
  "utf8",
);

/** Extrait les déclarations `--x: valeur;` du bloc qui suit `selector {`. */
function tokensOf(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start === -1) throw new Error(`bloc introuvable: ${selector}`);
  const open = css.indexOf("{", start);
  let depth = 1;
  let i = open + 1;
  while (depth > 0 && i < css.length) {
    if (css[i] === "{") depth++;
    if (css[i] === "}") depth--;
    i++;
  }
  const body = css.slice(open + 1, i - 1);
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    out[m[1]] = m[2].trim();
  }
  return out;
}

const light = tokensOf(":root {");
const darkExplicit = tokensOf(':root[data-theme="dark"]');
const darkAuto = tokensOf(':root:not([data-theme="light"])');

function color(tokens: Record<string, string>, name: string): Rgba {
  const raw = tokens[name] ?? light[name]; // le sombre hérite du clair s'il ne surcharge pas
  const c = raw ? parseCssColor(raw) : null;
  if (!c) throw new Error(`token non couleur: ${name} = ${raw}`);
  return c;
}

/** Compose une couleur (éventuellement alpha) sur le fond du thème. */
function onBg(tokens: Record<string, string>, name: string): Rgba {
  return composite(color(tokens, name), color(tokens, "--background"));
}

const themes: Array<[string, Record<string, string>]> = [
  ["clair", light],
  ["sombre", darkExplicit],
];

describe("les deux blocs sombres sont identiques", () => {
  it("media query dark === data-theme dark", () => {
    expect(darkAuto).toEqual(darkExplicit);
  });
});

describe.each(themes)("thème %s — texte >= 4.5:1", (_name, t) => {
  const bg = color(t, "--background");
  const card = onBg(t, "--card");

  it("foreground / background", () => {
    expect(contrastRatio(color(t, "--foreground"), bg)).toBeGreaterThanOrEqual(4.5);
  });
  it("foreground / card composité", () => {
    expect(contrastRatio(color(t, "--foreground"), card)).toBeGreaterThanOrEqual(4.5);
  });
  it("muted-foreground / background", () => {
    expect(contrastRatio(color(t, "--muted-foreground"), bg)).toBeGreaterThanOrEqual(4.5);
  });
  it("muted-foreground / card composité", () => {
    expect(contrastRatio(color(t, "--muted-foreground"), card)).toBeGreaterThanOrEqual(4.5);
  });
  it("primary-foreground / primary", () => {
    expect(
      contrastRatio(color(t, "--primary-foreground"), composite(color(t, "--primary"), bg)),
    ).toBeGreaterThanOrEqual(4.5);
  });
  it.each(["success", "warning", "destructive", "info", "tertiary"])(
    "%s-foreground / %s-muted composité",
    (sem) => {
      const fg = color(t, `--${sem}-foreground`);
      const surface = composite(color(t, `--${sem}-muted`), bg);
      expect(contrastRatio(fg, surface)).toBeGreaterThanOrEqual(4.5);
    },
  );
  it("nav-active-fg / lavis nav composité (ring 10% sur background)", () => {
    const ring = color(t, "--ring");
    const wash = composite({ ...ring, a: 0.1 }, bg);
    expect(contrastRatio(color(t, "--nav-active-fg"), wash)).toBeGreaterThanOrEqual(4.5);
  });
});

describe.each(themes)("thème %s — UI >= 3:1", (_name, t) => {
  const bg = color(t, "--background");
  // --border est décoratif (non porteur d'état) : hors périmètre du seuil UI 3:1 — seul --ring est audité.
  it("ring / background", () => {
    expect(contrastRatio(color(t, "--ring"), bg)).toBeGreaterThanOrEqual(3.0);
  });
});
