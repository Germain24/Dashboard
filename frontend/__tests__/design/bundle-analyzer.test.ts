/**
 * Garde : un script `analyze` produit le rapport @next/bundle-analyzer
 * (repérer les régressions de taille par route et les barrels qui tirent
 * un module entier), sans jamais s'activer pendant un build normal.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");
const pkg = JSON.parse(readFileSync(path.join(frontendRoot, "package.json"), "utf8"));
const nextConfig = readFileSync(path.join(frontendRoot, "next.config.ts"), "utf8");

describe("bundle analyzer", () => {
  it("package.json expose un script analyze qui active ANALYZE=true", () => {
    expect(pkg.scripts?.analyze).toBeDefined();
    expect(pkg.scripts.analyze).toMatch(/ANALYZE=true/);
    expect(pkg.scripts.analyze).toMatch(/next build/);
  });

  it("@next/bundle-analyzer est en devDependency (pas dependency de prod)", () => {
    expect(pkg.devDependencies?.["@next/bundle-analyzer"]).toBeDefined();
    expect(pkg.dependencies?.["@next/bundle-analyzer"]).toBeUndefined();
  });

  it("next.config.ts n'active l'analyzer que si ANALYZE=true (jamais par défaut)", () => {
    expect(nextConfig).toMatch(/@next\/bundle-analyzer/);
    expect(nextConfig).toMatch(/enabled:\s*process\.env\.ANALYZE\s*===\s*["']true["']/);
  });
});
