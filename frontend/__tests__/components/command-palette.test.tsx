import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "@/components/CommandPalette";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("CommandPalette", () => {
  it("expose une liste active navigable au clavier", () => {
    render(<CommandPalette />);
    act(() => {
      window.dispatchEvent(new Event("mc:command-palette"));
    });

    const input = screen.getByRole("combobox", { name: "Rechercher une commande" });
    const firstOption = screen.getAllByRole("option")[0];
    expect(input).toHaveAttribute("aria-controls", screen.getByRole("listbox").id);
    expect(firstOption).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    const activeId = input.getAttribute("aria-activedescendant");
    expect(activeId).toBe(screen.getAllByRole("option")[1].id);
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
  });

  it("annule une recherche distante dès que la saisie change", async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        signals.push(init?.signal as AbortSignal);
        return new Promise<Response>(() => {});
      }),
    );
    const { unmount } = render(<CommandPalette />);
    act(() => {
      window.dispatchEvent(new Event("mc:command-palette"));
    });
    const input = screen.getByRole("combobox", { name: "Rechercher une commande" });

    fireEvent.change(input, { target: { value: "budget" } });
    await act(async () => {
      vi.advanceTimersByTime(251);
      await Promise.resolve();
    });
    expect(signals).toHaveLength(1);
    expect(signals[0].aborted).toBe(false);

    fireEvent.change(input, { target: { value: "budget annuel" } });
    expect(signals[0].aborted).toBe(true);
    unmount();
  });
});
