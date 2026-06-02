// Types + client API pour le module Skincare (proxy Next -> backend)
const BASE = "/api/skincare";

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(`API ${r.status} ${detail}`);
  }
  return r.json() as Promise<T>;
}

export interface SkincareProduct {
  id: number;
  nom: string;
  type: string;
  moment: "AM" | "PM" | "les_deux";
  ordre: number;
  frequence_type: "quotidien" | "hebdo_jours" | "n_par_semaine";
  frequence_jours?: string | null;
  frequence_n?: number | null;
  apres_douche: boolean;
  soir_seulement: boolean;
  pas_avant_soleil: boolean;
  duree_min: number;
  stock_qte?: number | null;
  unite?: string | null;
  date_ouverture?: string | null;
  date_peremption?: string | null;
  cout: number;
  actif: boolean;
}

export interface SkincareToday {
  date: string;
  AM: SkincareProduct[];
  PM: SkincareProduct[];
  due: SkincareProduct[];
}

export const skincareApi = {
  list: (): Promise<SkincareProduct[]> => fetch(`${BASE}/products`).then((r) => json<SkincareProduct[]>(r)),
  today: (): Promise<SkincareToday> => fetch(`${BASE}/today`).then((r) => json<SkincareToday>(r)),
  toRepurchase: (): Promise<SkincareProduct[]> => fetch(`${BASE}/to-repurchase`).then((r) => json<SkincareProduct[]>(r)),
  create: (data: Partial<SkincareProduct>): Promise<SkincareProduct> =>
    fetch(`${BASE}/products`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<SkincareProduct>(r)),
  update: (id: number, data: Partial<SkincareProduct>): Promise<SkincareProduct> =>
    fetch(`${BASE}/products/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<SkincareProduct>(r)),
  remove: (id: number): Promise<Response> => fetch(`${BASE}/products/${id}`, { method: "DELETE" }),
};
