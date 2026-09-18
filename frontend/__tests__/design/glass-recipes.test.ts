/**
 * Garde : la matière verre passe par les recettes .glass-* de globals.css.
 * Aucun backdrop-filter ad hoc dans les composants.
 */
import { it, expect } from "vitest";
import { execSync } from "node:child_process";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

it("aucun backdrop-blur/saturate ad hoc dans les .tsx", () => {
  let out: string;
  try {
    out = execSync(
      'git grep -n "backdrop-blur\\|backdrop-saturate\\|backdrop-filter" -- "components/**/*.tsx" "components/*.tsx" "src/**/*.tsx" "src/*.tsx"',
      { cwd: frontendRoot, encoding: "utf8" },
    );
  } catch {
    out = ""; // git grep sort en code 1 quand zéro correspondance : c'est le succès
  }
  expect(out.trim(), `verre ad hoc trouvé:\n${out}`).toBe("");
});
