import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { MainShell } from "@/components/layout/MainShell";

const usePathname = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => usePathname() }));

afterEach(() => {
  cleanup();
  delete document.body.dataset.module;
});

describe("MainShell — data-module sur <body>", () => {
  it("pose le premier segment du pathname", () => {
    usePathname.mockReturnValue("/finance/positions");
    render(<MainShell>x</MainShell>);
    expect(document.body.dataset.module).toBe("finance");
  });

  it("retire l'attribut sur l'accueil", () => {
    usePathname.mockReturnValue("/garderobe");
    const { unmount } = render(<MainShell>x</MainShell>);
    expect(document.body.dataset.module).toBe("garderobe");
    unmount();
    usePathname.mockReturnValue("/");
    render(<MainShell>x</MainShell>);
    expect(document.body.dataset.module).toBeUndefined();
  });
});
