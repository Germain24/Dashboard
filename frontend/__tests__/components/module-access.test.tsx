import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ModuleAccess } from "@/components/layout/ModuleAccess";

const { mockUsePathname } = vi.hoisted(() => ({ mockUsePathname: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: mockUsePathname }));

let remoteAccess = { favorites: [] as string[], recents: [] as string[] };
let fetchMock: ReturnType<typeof vi.fn>;

describe("ModuleAccess", () => {
  beforeEach(() => {
    window.localStorage.clear();
    remoteAccess = { favorites: [], recents: [] };
    fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        const rawBody = typeof init.body === "string" ? init.body : "{}";
        const body = JSON.parse(rawBody) as {
          module_access: { favorites: string[]; recents: string[] };
        };
        remoteAccess = body.module_access;
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ preferences: { module_access: remoteAccess } }),
      } as Response);
    });
    vi.stubGlobal("fetch", fetchMock);
    mockUsePathname.mockReturnValue("/budget");
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("mémorise les modules récents et les retrouve depuis le Dock", async () => {
    const { unmount } = render(<ModuleAccess variant="dock" />);

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem("mc:module-recents:v1") ?? "[]")).toEqual([
        "budget",
      ]);
    });

    fireEvent.click(screen.getByRole("button", { name: /favoris et les modules récents/i }));

    const recentSection = screen.getByRole("region", { name: "Récemment ouverts" });
    expect(within(recentSection).getByRole("link", { name: /Budget/ })).toHaveAttribute(
      "href",
      "/budget",
    );
    unmount();
  });

  it("permet d'épingler un module depuis l'accueil et synchronise le favori", async () => {
    render(<ModuleAccess variant="home" />);

    fireEvent.click(screen.getByRole("button", { name: "Gérer" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ajouter Agenda aux favoris" }));

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem("mc:module-favorites:v1") ?? "[]")).toEqual([
        "agenda",
      ]);
    });
    expect(
      within(screen.getByRole("region", { name: "Tes modules" })).getByRole("link", {
        name: /Agenda/,
      }),
    ).toHaveAttribute("href", "/agenda");
    expect(screen.getByRole("region", { name: "Favoris" })).toHaveTextContent("Agenda");
  });

  it("filtre les modules par nom", async () => {
    render(<ModuleAccess variant="dock" />);
    fireEvent.click(screen.getByRole("button", { name: /favoris et les modules récents/i }));
    fireEvent.change(await screen.findByRole("searchbox", { name: "Filtrer les modules" }), {
      target: { value: "travail" },
    });

    expect(screen.getByRole("link", { name: "Travail" })).toHaveAttribute("href", "/travail");
    expect(screen.queryByRole("link", { name: "Budget" })).not.toBeInTheDocument();
  });

  it("charge les favoris depuis le backend partagé entre appareils", async () => {
    remoteAccess = { favorites: ["travail"], recents: ["budget"] };
    render(<ModuleAccess variant="home" />);

    const homeModules = screen.getByRole("region", { name: "Tes modules" });
    expect(await within(homeModules).findByRole("link", { name: /Travail/ })).toHaveAttribute(
      "href",
      "/travail",
    );
    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem("mc:module-favorites:v1") ?? "[]")).toEqual([
        "travail",
      ]);
    });
    await waitFor(() => expect(remoteAccess.recents).toContain("budget"));

    remoteAccess = { favorites: ["agenda"], recents: ["travail"] };
    fireEvent(window, new Event("focus"));
    expect(await within(homeModules).findByRole("link", { name: /Agenda/ })).toHaveAttribute(
      "href",
      "/agenda",
    );
    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem("mc:module-favorites:v1") ?? "[]")).toEqual([
        "agenda",
      ]);
    });
  });

  it("garde les préférences locales et autorise leur modification si l'API est hors ligne", async () => {
    window.localStorage.setItem("mc:module-favorites:v1", JSON.stringify(["budget"]));
    fetchMock.mockRejectedValue(new Error("offline"));
    render(<ModuleAccess variant="dock" />);

    fireEvent.click(screen.getByRole("button", { name: /favoris et les modules récents/i }));
    expect(
      await screen.findByText(/Hors ligne : les changements restent enregistrés/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ajouter Agenda aux favoris" }));

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem("mc:module-favorites:v1") ?? "[]")).toEqual([
        "budget",
        "agenda",
      ]);
    });
  });
});
