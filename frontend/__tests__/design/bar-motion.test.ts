/**
 * Garde : les barres de progression (remplissage via width inline) animent
 * leurs deltas à la revalidation TanStack — recette .bar-fill unique
 * (transition width sur --ease-out), pas de transition-all ad hoc.
 */
import { describe, it, expect } from "vitest";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");
const css = readFileSync(path.join(frontendRoot, "src/app/globals.css"), "utf8");

describe("barres — deltas animés sur tokens", () => {
  it("globals.css définit la recette .bar-fill (width sur --ease-out)", () => {
    const rule = css.match(/\.bar-fill\s*\{[^}]*\}/);
    expect(rule, "recette .bar-fill absente de globals.css").not.toBeNull();
    expect(rule![0]).toMatch(/transition:[^;]*width[^;]*var\(--ease-out\)/);
  });

  it("chaque remplissage de barre inline porte .bar-fill", () => {
    const files = execSync('git ls-files -- "components/**/*.tsx" "src/**/*.tsx"', {
      cwd: frontendRoot,
      encoding: "utf8",
    })
      .trim()
      .split("\n");
    const offenders: string[] = [];
    for (const file of files) {
      const source = readFileSync(path.join(frontendRoot, file), "utf8");
      const bars = (source.match(/width: `\$\{/g) ?? []).length;
      if (bars === 0) continue;
      const fills = (source.match(/bar-fill/g) ?? []).length;
      if (fills < bars) {
        offenders.push(`${file} (${bars} barres, ${fills} bar-fill)`);
      }
    }
    expect(offenders, `barres sans .bar-fill:\n${offenders.join("\n")}`).toEqual([]);
  });
});
