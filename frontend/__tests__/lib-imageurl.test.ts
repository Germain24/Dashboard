import { describe, it, expect } from "vitest";
import { imageUrl } from "@/lib/garderobe";

describe("imageUrl", () => {
  it("utilise image si présent", () => {
    expect(imageUrl({ id: "v1", image: "Haut/tee.png" })).toBe("/garderobe/assets/Haut/tee.png");
  });
  it("repli sur l'id si image nul", () => {
    expect(imageUrl({ id: "v1", image: null })).toBe("/garderobe/assets/v1.png");
  });
});
