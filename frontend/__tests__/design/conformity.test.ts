/**
 * Garde de conformité Verre Clair : les couleurs vivent dans les tokens
 * (globals.css) ou lib/design/colors.ts — jamais en dur dans les composants.
 * HEX_WHITELIST = dette connue (constat 2026-07-03), vidée lot par lot ;
 * le lot 6 l'asserte vide.
 */
import { it, expect } from "vitest";
import { execSync } from "node:child_process";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

export const HEX_WHITELIST = [
  "components/agenda/Agenda.tsx",
  "components/agenda/SemaineTab.tsx",
  "components/deck/modules/ScoreRingModule.tsx",
  "components/entrainement/AujourdhuiTab.tsx",
  "components/films/WatchlistSection.tsx",
  "components/garderobe/Garderobe.tsx",
  "components/garderobe/RecommandationsTab.tsx",
  "components/habitudes/AujourdhuiTab.tsx",
  "components/habitudes/GestionTab.tsx",
  "components/livres/BibliothequeTab.tsx",
  "components/musique/Bibliotheque.tsx",
  "components/sante/TendanceTab.tsx",
  "src/app/donnees/page.tsx",
  "src/app/layout.tsx",
  "src/app/score/page.tsx",
  "src/app/snapshot/page.tsx",
];

function gitGrepFiles(pattern: string): string[] {
  try {
    const out = execSync(
      `git grep -lE "${pattern}" -- "components/*.tsx" "src/*.tsx"`,
      { cwd: frontendRoot, encoding: "utf8" },
    );
    return out.trim().split("\n").filter(Boolean).map((f) => f.replace(/\\/g, "/"));
  } catch {
    return []; // git grep sort en code 1 quand zéro correspondance
  }
}

it("aucune couleur hex/rgb hardcodée hors whitelist", () => {
  const offenders = gitGrepFiles("#[0-9a-fA-F]{6}|rgb\\([0-9]").filter(
    (f) => !HEX_WHITELIST.includes(f),
  );
  expect(offenders, `couleurs hardcodées hors whitelist:\n${offenders.join("\n")}`).toEqual([]);
});
