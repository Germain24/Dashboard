/**
 * Garde : le mouvement des toasts sonner (entrée/sortie/empilement) est aligné
 * sur les tokens motion de l'app (--ease-out), pas sur le `ease` par défaut de
 * la lib. La surcharge ne doit pas neutraliser le drag (data-swiping).
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

const css = readFileSync(
  path.resolve(__dirname, "../../src/app/globals.css"),
  "utf8",
);

describe("toasts sonner — mouvement sur tokens", () => {
  it("surcharge la transition des toasts avec var(--ease-out)", () => {
    const rule = css.match(
      /\[data-sonner-toast\][^{]*\{[^}]*transition:[^}]*\}/,
    );
    expect(rule, "aucune surcharge [data-sonner-toast] dans globals.css").not.toBeNull();
    expect(rule![0]).toContain("var(--ease-out)");
  });

  it("préserve le drag : la surcharge exclut data-swiping", () => {
    const rule = css.match(/\[data-sonner-toast\][^{]*\{[^}]*transition:[^}]*\}/);
    expect(rule![0]).toContain(":not([data-swiping");
  });

  it("aligne aussi le repositionnement du toaster (lift) sur --ease-out", () => {
    const rule = css.match(
      /\[data-sonner-toaster\][^{]*\{[^}]*transition:[^}]*\}/,
    );
    expect(rule, "aucune surcharge [data-sonner-toaster] dans globals.css").not.toBeNull();
    expect(rule![0]).toContain("var(--ease-out)");
  });
});
