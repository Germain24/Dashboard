import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { voyageApi } from "@/lib/voyage";
import { useLieuxVoyage } from "@/lib/queries/voyage";

vi.mock("@/lib/voyage", () => ({
  voyageApi: {
    listLieux: vi.fn(),
    sync: vi.fn(),
    planifier: vi.fn(),
    confirmer: vi.fn(),
  },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useLieuxVoyage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("charge la liste des lieux", async () => {
    vi.mocked(voyageApi.listLieux).mockResolvedValue([
      { id: 1, nom: "Table Mountain", ville: "Le Cap", pays: "Afrique du Sud", visite: false,
        aeroport_iata: "CPT", jours_min: 2, jours_max: 4, cout_jour_estime: 80, complet: true },
    ]);

    const { result } = renderHook(() => useLieuxVoyage(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].nom).toBe("Table Mountain");
  });
});
