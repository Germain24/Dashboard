/**
 * Garde : toutes les images passent par next/image (optimisation, lazy
 * loading, zéro layout shift) — jamais de balise <img> brute.
 */
import { it, expect } from "vitest";
import { execSync } from "node:child_process";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

it("aucune balise <img> brute dans components/ ou src/", () => {
  let out: string;
  try {
    out = execSync(
      'git grep --untracked -n "<img\\b" -- "components/**/*.tsx" "components/*.tsx" "src/**/*.tsx" "src/*.tsx"',
      { cwd: frontendRoot, encoding: "utf8" },
    );
  } catch {
    out = ""; // git grep sort en code 1 quand zéro correspondance : c'est le succès
  }
  expect(out.trim(), `<img> brute trouvée (utiliser next/image) :\n${out}`).toBe("");
});
