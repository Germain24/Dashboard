/**
 * Garde de conformité Verre Clair : les couleurs vivent dans les tokens
 * (globals.css) ou lib/design/colors.ts — jamais en dur dans les composants.
 * HEX_WHITELIST = dette connue (constat 2026-07-03), vidée lot par lot ;
 * lot 5 (Loisirs + transverse) retire les 7 dernières entrées, le lot 6
 * asserte qu'elle reste vide.
 */
import { it, expect } from "vitest";
import { execFileSync } from "node:child_process";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

export const HEX_WHITELIST: string[] = [];

function gitGrepFiles(pattern: string): string[] {
  try {
    // execFileSync (argv direct, pas de shell) : sur Windows, execSync passe
    // par cmd.exe dont le parsing de guillemets imbriqués corrompt les patterns
    // contenant des ["'`] (cf. HEX_WHITELIST au-dessus) — execFileSync évite
    // complètement le shell, donc plus de souci d'échappement quel que soit l'OS.
    const out = execFileSync(
      "git",
      ["grep", "-lE", pattern, "--", "components/*.tsx", "src/*.tsx"],
      { cwd: frontendRoot, encoding: "utf8" },
    );
    return out.trim().split("\n").filter(Boolean).map((f) => f.replace(/\\/g, "/"));
  } catch (err) {
    // git grep sort en code 1 quand zéro correspondance (succès, pas une erreur) ;
    // tout autre code (git absent, cwd cassé, etc.) doit faire échouer le test.
    if ((err as { status?: number }).status === 1) return [];
    throw err;
  }
}

it("aucune couleur hex/rgb hardcodée hors whitelist", () => {
  // Ancré sur un guillemet/apostrophe/backtick précédant le hex : les vraies
  // couleurs hex sont toujours des littéraux de chaîne ('#fff', "#04142c", …).
  // Un pattern non ancré (#[0-9a-fA-F]{3}\b nu) matche aussi les refs d'issues
  // en commentaire (#546, #114, #547…) puisque tout chiffre 0-9 est un digit
  // hex valide — faux positifs massifs sans rapport avec la conformité couleur.
  const offenders = gitGrepFiles(`["'\`]#[0-9a-fA-F]{6}|["'\`]#[0-9a-fA-F]{3}\\b|rgb\\([0-9]`).filter(
    (f) => !HEX_WHITELIST.includes(f),
  );
  expect(offenders, `couleurs hardcodées hors whitelist:\n${offenders.join("\n")}`).toEqual([]);
});

it("la whitelist de couleurs est vide (dette résorbée)", () => {
  expect(HEX_WHITELIST).toEqual([]);
});

it("classe CSS .stagger disparue (migrée vers StaggerGroup)", () => {
  const offenders = gitGrepFiles(`["' ]stagger["' ]`);
  expect(offenders, `usages .stagger restants:\n${offenders.join("\n")}`).toEqual([]);
});
