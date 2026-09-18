import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const queryHooks = vi.hoisted(() => ({
  useNotifications: vi.fn(),
  useNotifPrefs: vi.fn(),
  useClearNotifications: vi.fn(),
  useMarkAllRead: vi.fn(),
  useMarkRead: vi.fn(),
  useSetNotifPref: vi.fn(),
}));

vi.mock("@/lib/queries/jobs", () => queryHooks);

import { NotificationsWidget } from "@/components/layout/NotificationsWidget";

describe("NotificationsWidget", () => {
  const clear = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    queryHooks.useNotifications.mockReturnValue({
      data: [{ id: 1, titre: "Rappel", message: "À faire", lu: false }],
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    });
    queryHooks.useNotifPrefs.mockReturnValue({ data: [], isPending: false, isError: false, refetch: vi.fn() });
    queryHooks.useClearNotifications.mockReturnValue({ mutate: clear, isPending: false, isError: false });
    queryHooks.useMarkAllRead.mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false });
    queryHooks.useMarkRead.mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false });
    queryHooks.useSetNotifPref.mockReturnValue({ mutate: vi.fn() });
  });

  it("demande confirmation avant de supprimer toutes les notifications", () => {
    render(<NotificationsWidget />);
    fireEvent.click(screen.getByRole("button", { name: "Notifications, 1 non lues" }));
    fireEvent.click(screen.getByRole("button", { name: "Tout effacer" }));

    expect(clear).not.toHaveBeenCalled();
    expect(screen.getByRole("group", { name: "Confirmation de suppression des notifications" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Effacer" }));
    expect(clear).toHaveBeenCalledOnce();
  });

  it("distingue le chargement d'un état réellement vide", () => {
    queryHooks.useNotifications.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isFetching: true,
      refetch: vi.fn(),
    });
    render(<NotificationsWidget />);
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByRole("status")).toHaveTextContent("Chargement des notifications");
    expect(screen.queryByText("Aucune notification")).not.toBeInTheDocument();
  });
});
