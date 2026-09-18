import { describe, expect, it } from "vitest";
import { buildConfirmerRequest, type Itineraire } from "@/lib/voyage";

const etape = (over: Partial<Itineraire["etapes"][number]>) => ({
  lieu_id: 1, nom: "Table Mountain", pays: "Afrique du Sud", jours: 3,
  date_arrivee: "2026-08-02", date_depart: "2026-08-05", lat: null, lon: null,
  ...over,
});

const itineraire = (etapes: Itineraire["etapes"]): Itineraire => ({
  etapes, cout_total: 0, cout_transport: 0, cout_sejour: 0,
  depart: { iata: "YUL", lat: null, lon: null },
  arrivee: { iata: "YUL", lat: null, lon: null },
});

describe("buildConfirmerRequest", () => {
  it("transmet les lieux et les étapes datées", () => {
    const req = buildConfirmerRequest(
      itineraire([etape({}), etape({ lieu_id: 2, nom: "Kruger", jours: 4 })]),
      { dateDebut: "2026-08-01", dateFin: "2026-08-15", departIata: "YUL" },
    );

    expect(req.lieu_ids).toEqual([1, 2]);
    expect(req.etapes).toEqual([
      { lieu_id: 1, jours: 3, date_arrivee: "2026-08-02", date_depart: "2026-08-05" },
      { lieu_id: 2, jours: 4, date_arrivee: "2026-08-02", date_depart: "2026-08-05" },
    ]);
    expect(req.date_debut).toBe("2026-08-01");
    expect(req.depart_iata).toBe("YUL");
  });

  it("titre les voyages par pays visités, sans doublon", () => {
    const req = buildConfirmerRequest(
      itineraire([
        etape({}),
        etape({ lieu_id: 2, nom: "Kruger" }),
        etape({ lieu_id: 3, nom: "Victoria Falls", pays: "Zambie" }),
      ]),
      { dateDebut: "2026-08-01", dateFin: "2026-08-15", departIata: "YUL" },
    );
    expect(req.titre).toBe("Afrique du Sud · Zambie");
  });

  it("retombe sur le nom du lieu quand le pays manque", () => {
    const req = buildConfirmerRequest(
      itineraire([etape({ pays: null })]),
      { dateDebut: "2026-08-01", dateFin: "2026-08-15", departIata: "YUL" },
    );
    expect(req.titre).toBe("Table Mountain");
  });

  it("tronque un titre à rallonge", () => {
    const req = buildConfirmerRequest(
      itineraire([
        etape({ lieu_id: 1, pays: "A" }), etape({ lieu_id: 2, pays: "B" }),
        etape({ lieu_id: 3, pays: "C" }), etape({ lieu_id: 4, pays: "D" }),
      ]),
      { dateDebut: "2026-08-01", dateFin: "2026-08-15", departIata: "YUL" },
    );
    expect(req.titre).toBe("A · B · C +1");
  });

  it("utilise le départ comme arrivée par défaut", () => {
    const req = buildConfirmerRequest(itineraire([etape({})]), {
      dateDebut: "2026-08-01", dateFin: "2026-08-15", departIata: "YUL",
    });
    expect(req.arrivee_iata).toBe("YUL");

    const retour = buildConfirmerRequest(itineraire([etape({})]), {
      dateDebut: "2026-08-01", dateFin: "2026-08-15", departIata: "YUL", arriveeIata: "CDG",
    });
    expect(retour.arrivee_iata).toBe("CDG");
  });
});
