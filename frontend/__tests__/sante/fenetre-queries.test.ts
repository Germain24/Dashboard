import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du helper HTTP `api` (hoisted → référence sûre dans la factory vi.mock).
const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: apiMock }));

import { santeApi } from "@/lib/sante";

beforeEach(() => {
  apiMock.mockReset();
  apiMock.mockResolvedValue({
    anchor_date: "2026-07-20",
    length: 3,
    jours: [],
    shopping_list: [],
    score: {},
  });
});

describe("fenetre client", () => {
  it("POST generate hits the right endpoint", async () => {
    await santeApi.generateFenetre({ date: "2026-07-20", poids: 51 });
    expect(apiMock.mock.calls[0][0]).toBe("/sante/fenetre/generate");
    expect(apiMock.mock.calls[0][1].method).toBe("POST");
  });

  it("GET current passes the date param", async () => {
    await santeApi.fenetreCurrent("2026-07-21");
    expect(apiMock.mock.calls[0][0]).toContain("/sante/fenetre/current");
    expect(apiMock.mock.calls[0][0]).toContain("date=2026-07-21");
  });

  it("GET current without date hits the bare endpoint", async () => {
    await santeApi.fenetreCurrent();
    expect(apiMock.mock.calls[0][0]).toBe("/sante/fenetre/current");
  });
});
