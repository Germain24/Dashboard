import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WalkmanSyncProgress } from "@/lib/musique";

const mocks = vi.hoisted(() => ({
  status: null as WalkmanSyncProgress | null,
  start: vi.fn(),
}));

vi.mock("next/image", () => ({
  default: (props: React.ImgHTMLAttributes<HTMLImageElement>) => (
    <img {...props} alt={props.alt ?? ""} />
  ),
}));
vi.mock("@/lib/musique", () => ({
  mediaUrl: (path: string) => path,
  musiqueApi: { progress: vi.fn().mockResolvedValue({ active: false, n_done: 0, n_total: 0 }) },
}));
vi.mock("@/components/RealtimeProvider", () => ({ useRealtimeEvent: vi.fn() }));
vi.mock("@/lib/queries/musique", () => ({
  musiqueKeys: { walkmanSyncStatus: () => ["musique", "walkman-sync-status"] },
  useTracks: () => ({ data: [] }),
  useScanLibrary: () => ({ isPending: false, mutate: vi.fn() }),
  useClassify: () => ({ mutate: vi.fn() }),
  useResetClassify: () => ({ mutate: vi.fn() }),
  useWalkmanSyncStatus: () => ({ data: mocks.status, isError: false }),
  useStartWalkmanSync: () => ({
    mutate: mocks.start,
    isPending: false,
    isError: false,
    error: null,
  }),
}));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ setQueryData: vi.fn() }) }));

import { Bibliotheque } from "@/components/musique/Bibliotheque";

function makeProgress(overrides: Partial<WalkmanSyncProgress> = {}): WalkmanSyncProgress {
  return {
    active: false,
    status: "idle",
    phase: null,
    n_done: 0,
    n_total: 0,
    current_file: null,
    copied: 0,
    converted: 0,
    identical: 0,
    replaced: 0,
    skipped_priority: 0,
    skipped_capacity: 0,
    failed: 0,
    error: null,
    ...overrides,
  };
}

describe("Bibliothèque — synchronisation Walkman", () => {
  beforeEach(() => {
    mocks.status = makeProgress();
    mocks.start.mockReset();
  });

  it("lance la synchronisation depuis le bouton", () => {
    render(<Bibliotheque />);
    fireEvent.click(screen.getByRole("button", { name: "Synchroniser le Walkman" }));
    expect(mocks.start).toHaveBeenCalledOnce();
  });

  it("affiche la phase et la progression active", () => {
    mocks.status = makeProgress({
      active: true,
      status: "running",
      phase: "converting",
      n_done: 2,
      n_total: 4,
      current_file: "Artiste/Album/Titre.m4a",
      converted: 1,
    });
    render(<Bibliotheque />);

    expect(screen.getByText("Conversion AAC")).toBeInTheDocument();
    expect(screen.getByText("2 / 4 morceaux")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Artiste/Album/Titre.m4a")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Synchronisation…" })).toBeDisabled();
  });

  it("affiche les comptes finaux et l'erreur du job", () => {
    mocks.status = makeProgress({
      status: "failed",
      failed: 2,
      copied: 4,
      converted: 3,
      identical: 1,
      replaced: 2,
      skipped_capacity: 5,
      error: "Le Walkman a été déconnecté.",
    });
    render(<Bibliotheque />);

    expect(screen.getByText("Synchronisation interrompue")).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName === "P" &&
          element.textContent?.includes("Le Walkman a été déconnecté.") === true,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("5", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("Hors capacité")).toBeInTheDocument();
  });
});
