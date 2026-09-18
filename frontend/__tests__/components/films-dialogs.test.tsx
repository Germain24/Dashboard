import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { WatchItem } from "@/lib/films";

const mocks = vi.hoisted(() => ({
  addMutate: vi.fn(),
  updateProgressMutate: vi.fn(),
}));

vi.mock("@/lib/queries/films", () => ({
  useWatchlist: () => ({ data: [], isError: false }),
  useWatchStats: () => ({ data: null }),
  useAddWatchItem: () => ({ mutate: mocks.addMutate, isPending: false }),
  useUpdateWatchItem: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteWatchItem: () => ({ mutate: vi.fn(), isPending: false }),
  useSerieProgress: () => ({ data: null, isLoading: false }),
  useUpdateProgress: () => ({ mutate: mocks.updateProgressMutate, isPending: false }),
}));

import WatchlistSection from "@/components/films/WatchlistSection";
import SeriesProgressModal from "@/components/films/SeriesProgressModal";

describe("modals Films & Séries", () => {
  it("donne un titre accessible et restaure le focus après Échap", async () => {
    render(<WatchlistSection mediaType="film" />);
    const trigger = screen.getByRole("button", { name: "Ajouter" });
    trigger.focus();
    fireEvent.click(trigger);

    expect(screen.getByRole("dialog", { name: "Ajouter un film" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("conserve le titre et la sauvegarde de progression de série", () => {
    const onClose = vi.fn();
    const serie = { id: 42, titre: "Severance", nb_saisons: 3 } as WatchItem;
    render(<SeriesProgressModal serie={serie} onClose={onClose} />);

    expect(screen.getByRole("dialog", { name: "Progression — Severance" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sauvegarder" }));
    expect(mocks.updateProgressMutate).toHaveBeenCalledWith(
      [42, { saison: 1, episode_courant: 0 }],
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
