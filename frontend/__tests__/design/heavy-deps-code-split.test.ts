/**
 * Garde : Leaflet (carte du module voyage) ne doit jamais atterrir dans le
 * bundle commun. Un seul fichier l'importe (ItineraryMap.tsx), et tout
 * consommateur doit le charger via next/dynamic({ ssr: false }) — jamais un
 * import statique qui le tirerait dans le chunk de la route/layout parent.
 */
import { it, expect } from "vitest";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

function filesImporting(pkg: string): string[] {
  try {
    const out = execSync(
      `git grep -l "from [\\"']${pkg}[\\"']" -- "components/**/*.tsx" "src/**/*.tsx"`,
      { cwd: frontendRoot, encoding: "utf8" },
    );
    return out.trim().split("\n").filter(Boolean);
  } catch {
    return [];
  }
}

it("leaflet/react-leaflet ne sont importés que par ItineraryMap.tsx", () => {
  const offenders = [...filesImporting("leaflet"), ...filesImporting("react-leaflet")]
    .filter((f) => !f.endsWith("components/voyage/ItineraryMap.tsx"));
  expect(offenders, `import direct hors ItineraryMap.tsx:\n${offenders.join("\n")}`).toEqual([]);
});

it("ItineraryMap n'est jamais importé statiquement (seulement via next/dynamic ssr:false)", () => {
  const out = execSync('git grep -ln "ItineraryMap" -- "components/**/*.tsx" "src/**/*.tsx"', {
    cwd: frontendRoot,
    encoding: "utf8",
  });
  const consumers = out
    .trim()
    .split("\n")
    .filter((f) => f && !f.endsWith("components/voyage/ItineraryMap.tsx"));
  for (const file of consumers) {
    const source = readFileSync(path.join(frontendRoot, file), "utf8");
    const staticImport = /import\s*\{[^}]*ItineraryMap[^}]*\}\s*from\s*["']\.\/ItineraryMap["']/;
    expect(source, `${file} importe ItineraryMap statiquement`).not.toMatch(staticImport);
    expect(source, `${file} utilise ItineraryMap sans dynamic({ ssr: false })`).toMatch(
      /dynamic\(\s*\(\)\s*=>\s*import\(["']\.\/ItineraryMap["']\)[\s\S]*?ssr:\s*false/,
    );
  }
});
