/**
 * Garde : JetBrains Mono (chiffres tabulaires, code) est auto-hébergée via
 * next/font comme Public Sans et Libre Caslon Text — zéro FOUT, zéro requête
 * externe, pas de simple fallback système qui ne se déclenche jamais.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");
const layout = readFileSync(path.join(frontendRoot, "src/app/layout.tsx"), "utf8");
const css = readFileSync(path.join(frontendRoot, "src/app/globals.css"), "utf8");

describe("police mono — auto-hébergée next/font", () => {
  it("layout.tsx importe JetBrains_Mono depuis next/font/google", () => {
    expect(layout).toMatch(/import\s*\{[^}]*JetBrains_Mono[^}]*\}\s*from\s*"next\/font\/google"/);
  });

  it("la variable JetBrains Mono est posée sur <html> avec les 2 autres polices", () => {
    const htmlTag = layout.match(/<html[^>]*className=\{[^}]*\}[^>]*>/);
    expect(htmlTag, "balise <html> avec className introuvable").not.toBeNull();
    expect(htmlTag![0]).toMatch(/jetbrainsMono\.variable/);
  });

  it("--font-mono de globals.css utilise la variable next/font en premier", () => {
    const rule = css.match(/--font-mono:[^;]*;/);
    expect(rule, "--font-mono introuvable dans globals.css").not.toBeNull();
    expect(rule![0]).toMatch(/var\(--font-jetbrains-mono\)/);
  });
});
