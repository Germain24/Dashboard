import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { AgendaJour } from "@/lib/agenda";

let mockData: AgendaJour;

vi.mock("@/lib/queries/agenda", () => ({
  useAgendaToday: () => ({ data: mockData, isError: false, refetch: vi.fn() }),
  useMarkTaskDone: () => ({ mutate: vi.fn() }),
}));

import { TodayPanel } from "@/components/home/TodayPanel";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const baseTraining = {
  id: null,
  titre: "Entraînement — Lower",
  debut: "2026-07-07T00:00:00",
  fin: null as string | null,
  lieu: "Gym",
  description: "Séance planifiée : Lower · horaire libre",
  source: "entrainement",
  source_id: null,
  categorie: "sport",
  couleur: "#F59E0B",
  recurrence_id: null,
  is_virtual: true,
};

describe("TodayPanel — séance d'entraînement planifiée (#00h00)", () => {
  it("n'affiche pas la séance planifiée (fin=null) dans la liste — pas de 00 h 00", () => {
    mockData = {
      date: "2026-07-07",
      evenements: [
        {
          id: 1,
          titre: "Cours INF1000",
          debut: "2026-07-07T09:00:00",
          fin: "2026-07-07T10:00:00",
          lieu: null,
          description: null,
          source: "manuel",
          source_id: null,
          categorie: "cours",
          couleur: null,
          recurrence_id: null,
          is_virtual: false,
        },
      ],
      seance_entrainement: { ...baseTraining },
      slots_libres: [],
      taches_urgentes: [],
    };

    render(<TodayPanel />, { wrapper });

    // La séance planifiée (flexible, sans heure réelle) ne doit pas apparaître.
    expect(screen.queryByText("Entraînement — Lower")).not.toBeInTheDocument();
    // Le seul événement affiché est le cours réel.
    expect(screen.getByText("Cours INF1000")).toBeInTheDocument();
  });

  it("affiche bien la séance quand elle est loggée (fin non-null)", () => {
    mockData = {
      date: "2026-07-07",
      evenements: [],
      seance_entrainement: {
        ...baseTraining,
        debut: "2026-07-07T17:30:00",
        fin: "2026-07-07T18:15:00",
      },
      slots_libres: [],
      taches_urgentes: [],
    };

    render(<TodayPanel />, { wrapper });

    expect(screen.getByText("Entraînement — Lower")).toBeInTheDocument();
  });
});
