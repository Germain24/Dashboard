import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DatePicker } from "@/components/ui/date-picker";

describe("DatePicker", () => {
  it("annonce le calendrier et permet de le parcourir au clavier sans franchir la date minimale", async () => {
    render(
      <DatePicker
        label="Date de début"
        value="2026-09-12"
        min="2026-09-12"
        onChange={() => {}}
      />,
    );

    fireEvent.click(screen.getByLabelText("Date de début"));

    const calendar = screen.getByRole("dialog", { name: "Calendrier — Date de début" });
    const firstAllowedDate = calendar.querySelector<HTMLButtonElement>(
      '[data-calendar-date="2026-09-12"]',
    );
    expect(firstAllowedDate).not.toBeNull();
    expect(screen.getByRole("button", { name: "Mois précédent" })).toBeDisabled();

    await waitFor(() => expect(firstAllowedDate).toHaveFocus());
    fireEvent.keyDown(firstAllowedDate!, { key: "ArrowLeft" });
    await waitFor(() => expect(firstAllowedDate).toHaveFocus());

    fireEvent.keyDown(firstAllowedDate!, { key: "ArrowRight" });
    const nextDate = calendar.querySelector<HTMLButtonElement>('[data-calendar-date="2026-09-13"]');
    await waitFor(() => expect(nextDate).toHaveFocus());
  });

  it("sélectionne la date choisie et rend le focus au champ", async () => {
    const onChange = vi.fn();
    render(
      <DatePicker
        label="Date de fin"
        value="2026-09-12"
        min="2026-09-12"
        onChange={onChange}
      />,
    );

    const trigger = screen.getByLabelText("Date de fin");
    fireEvent.click(trigger);
    const date = screen.getByRole("button", { name: "dimanche 13 septembre 2026" });
    fireEvent.click(date);

    expect(onChange).toHaveBeenCalledWith("2026-09-13");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.queryByRole("dialog", { name: "Calendrier — Date de fin" })).not.toBeInTheDocument();
  });
});
