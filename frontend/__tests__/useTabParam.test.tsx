import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const push = vi.fn();
let search = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/finance",
  useSearchParams: () => new URLSearchParams(search),
}));

import { useTabParam } from "@/lib/useTabParam";

describe("useTabParam", () => {
  beforeEach(() => {
    push.mockClear();
    search = "";
  });

  it("retombe sur le défaut quand ?tab= est absent", () => {
    const { result } = renderHook(() => useTabParam<"suivi" | "buffett">("suivi"));
    expect(result.current[0]).toBe("suivi");
  });

  it("lit l'onglet depuis l'URL", () => {
    search = "tab=buffett";
    const { result } = renderHook(() => useTabParam<"suivi" | "buffett">("suivi"));
    expect(result.current[0]).toBe("buffett");
  });

  it("écrit l'onglet dans l'URL et garde le scroll", () => {
    const { result } = renderHook(() => useTabParam<"suivi" | "buffett">("suivi"));
    act(() => result.current[1]("buffett"));
    expect(push).toHaveBeenCalledWith("/finance?tab=buffett", { scroll: false });
  });

  it("retire ?tab= quand on revient à l'onglet par défaut (URL propre)", () => {
    search = "tab=buffett";
    const { result } = renderHook(() => useTabParam<"suivi" | "buffett">("suivi"));
    act(() => result.current[1]("suivi"));
    expect(push).toHaveBeenCalledWith("/finance", { scroll: false });
  });

  it("ignore une valeur d'URL hors de la liste autorisée", () => {
    search = "tab=inconnu";
    const { result } = renderHook(() =>
      useTabParam("suivi", { allowed: ["suivi", "buffett"] as const }),
    );
    expect(result.current[0]).toBe("suivi");
  });
});
