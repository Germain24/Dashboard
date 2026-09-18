import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { voyageApi, type VoyageConfirme } from "@/lib/voyage";
import { VoyagesConfirmesTab } from "@/components/voyage/VoyagesConfirmesTab";

vi.mock("@/lib/voyage", () => ({
  voyageApi: {
    listVoyages: vi.fn(),
    deleteVoyage: vi.fn(),
    setCoutReel: vi.fn(),
    addChecklistItem: vi.fn(),
    updateChecklistItem: vi.fn(),
    deleteChecklistItem: vi.fn(),
  },
}));

const VOYAGE: VoyageConfirme = {
  id: 1,
  titre: "Afrique du Sud",
  date_debut: "2026-08-01",
  date_fin: "2026-08-15",
  depart_iata: "YUL",
  arrivee_iata: null,
  etapes: [
    {
      id: 10, lieu_id: 3, nom: "Table Mountain", ville: "Le Cap", pays: "Afrique du Sud",
      ordre: 0, jours: 3, date_arrivee: "2026-08-02", date_depart: "2026-08-05",
      cout_estime: 380, cout_reel: null,
    },
    {
      id: 11, lieu_id: 4, nom: "Kruger", ville: null, pays: "Afrique du Sud",
      ordre: 1, jours: 4, date_arrivee: "2026-08-06", date_depart: "2026-08-10",
      cout_estime: 620, cout_reel: 700,
    },
  ],
  checklist: [
    { id: 20, label: "Passeport valide", fait: true, ordre: 0 },
    { id: 21, label: "Assurance voyage", fait: false, ordre: 1 },
  ],
  budget: {
    cout_estime_total: 1000, cout_reel_total: 700,
    cout_projete_total: 1080, ecart: 80, etapes_avec_cout_reel: 1,
  },
  checklist_total: 2,
  checklist_faits: 1,
};

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("VoyagesConfirmesTab", () => {
  beforeEach(() => vi.clearAllMocks());

  it("affiche les étapes avec leur budget estimé et réel", async () => {
    vi.mocked(voyageApi.listVoyages).mockResolvedValue([VOYAGE]);
    render(<VoyagesConfirmesTab />, { wrapper });

    expect(await screen.findByText("Afrique du Sud")).toBeInTheDocument();
    expect(screen.getByText("Table Mountain")).toBeInTheDocument();
    expect(screen.getByText("Kruger")).toBeInTheDocument();
    // Estimé par étape (2) + total du voyage (1).
    expect(screen.getAllByText(/estimé/i)).toHaveLength(3);
    // Projeté = 380 estimé + 700 réel (l'estimé de Kruger est remplacé).
    expect(screen.getByText(/1\s080/)).toBeInTheDocument();
    // Le coût réel saisi pré-remplit le champ de son étape.
    expect(screen.getByLabelText("Coût réel — Kruger")).toHaveValue(700);
    expect(screen.getByLabelText("Coût réel — Table Mountain")).toHaveValue(null);
  });

  it("affiche l'écart budgétaire sur l'étape et sur le total", async () => {
    vi.mocked(voyageApi.listVoyages).mockResolvedValue([VOYAGE]);
    render(<VoyagesConfirmesTab />, { wrapper });

    // 700 - 620 sur Kruger, et le même écart remonté au total du voyage.
    await waitFor(() => expect(screen.getAllByText(/\+80/)).toHaveLength(2));
  });

  it("affiche la progression de la checklist", async () => {
    vi.mocked(voyageApi.listVoyages).mockResolvedValue([VOYAGE]);
    render(<VoyagesConfirmesTab />, { wrapper });

    expect(await screen.findByText(/1\s*\/\s*2/)).toBeInTheDocument();
    expect(screen.getByLabelText("Passeport valide")).toBeChecked();
    expect(screen.getByLabelText("Assurance voyage")).not.toBeChecked();
  });

  it("coche un item de checklist", async () => {
    vi.mocked(voyageApi.listVoyages).mockResolvedValue([VOYAGE]);
    vi.mocked(voyageApi.updateChecklistItem).mockResolvedValue({
      id: 21, label: "Assurance voyage", fait: true, ordre: 1,
    });
    render(<VoyagesConfirmesTab />, { wrapper });

    fireEvent.click(await screen.findByLabelText("Assurance voyage"));
    await waitFor(() =>
      expect(voyageApi.updateChecklistItem).toHaveBeenCalledWith(1, 21, { fait: true }),
    );
  });

  it("enregistre un coût réel par étape", async () => {
    vi.mocked(voyageApi.listVoyages).mockResolvedValue([VOYAGE]);
    vi.mocked(voyageApi.setCoutReel).mockResolvedValue({ ...VOYAGE.etapes[0], cout_reel: 400 });
    render(<VoyagesConfirmesTab />, { wrapper });

    const input = await screen.findByLabelText("Coût réel — Table Mountain");
    fireEvent.change(input, { target: { value: "400" } });
    fireEvent.blur(input);

    await waitFor(() => expect(voyageApi.setCoutReel).toHaveBeenCalledWith(1, 10, 400));
  });

  it("affiche un état vide quand aucun voyage n'est confirmé", async () => {
    vi.mocked(voyageApi.listVoyages).mockResolvedValue([]);
    render(<VoyagesConfirmesTab />, { wrapper });

    expect(await screen.findByText(/aucun voyage confirmé/i)).toBeInTheDocument();
  });
});
