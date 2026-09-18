import { fireEvent, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KeyboardShortcuts } from "@/components/KeyboardShortcuts";

const navigation = vi.hoisted(() => ({ push: vi.fn(), pathname: "/agenda" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: navigation.push }),
  usePathname: () => navigation.pathname,
}));

beforeEach(() => {
  navigation.push.mockClear();
  navigation.pathname = "/agenda";
});

describe("KeyboardShortcuts", () => {
  it("suspend la navigation globale tant qu'un dialogue est ouvert", () => {
    const { rerender } = render(
      <>
        <div role="dialog" aria-modal="true" aria-label="Dialogue ouvert" />
        <KeyboardShortcuts />
      </>,
    );

    fireEvent.keyDown(window, { key: "j" });
    expect(navigation.push).not.toHaveBeenCalled();

    rerender(<KeyboardShortcuts />);
    fireEvent.keyDown(window, { key: "j" });
    expect(navigation.push).toHaveBeenCalledWith("/score");
  });

  it("limite les raccourcis de secteur aux quatre secteurs du Deck", () => {
    const goto = vi.fn();
    window.addEventListener("mc:deck-goto", goto);
    render(<KeyboardShortcuts />);

    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "4" });
    expect(goto).toHaveBeenLastCalledWith(expect.objectContaining({ detail: 3 }));

    goto.mockClear();
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "5" });
    expect(goto).not.toHaveBeenCalled();
    window.removeEventListener("mc:deck-goto", goto);
  });
});
