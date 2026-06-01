"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Shirt, Sparkles, PieChart, Clock } from "lucide-react";
import {
  garderobeApi,
  type SlotInfo,
  type StatsResponse,
  type SuggestResponse,
  type TenueHistory,
  type Recommendation,
  type Vetement,
  type Weather,
} from "@/lib/garderobe";
import { SlotCard } from "./SlotCard";
import { WeatherBanner } from "./WeatherBanner";
import { ThermalScore } from "./ThermalScore";
import { InventaireTab } from "./InventaireTab";
import { StatsTab } from "./StatsTab";
import { HistoriqueTab } from "./HistoriqueTab";
import { RecommandationsTab } from "./RecommandationsTab";

type Tab = "tenue" | "inventaire" | "stats" | "history" | "recs";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "inventaire", label: "Inventaire", Icon: Shirt },
  { id: "recs", label: "Recommandations", Icon: Sparkles },
  { id: "stats", label: "Stats", Icon: PieChart },
  { id: "history", label: "Historique", Icon: Clock },
];

const SLOT_ROW_1 = ["Manteau", "Veste", "Haut", "Pantalon", "Chaussures", "Echarpe"];
const SLOT_ROW_2 = ["Casquette", "Lunettes", "Bijoux 1", "Bijoux 2", "Montre", "Pendentif"];

const LAST_SUGGESTION_KEY = "garderobe:lastSuggestionDate";

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function Garderobe() {
  const [tab, setTab] = useState<Tab>("inventaire");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [slots, setSlots] = useState<SlotInfo[]>([]);
  const [wardrobe, setWardrobe] = useState<Vetement[]>([]);
  const [weather, setWeather] = useState<Weather | null>(null);
  const [suggestion, setSuggestion] = useState<SuggestResponse | null>(null);
  const [tenue, setTenue] = useState<Record<string, Vetement | null>>({});
  const [useBody, setUseBody] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [history, setHistory] = useState<TenueHistory[]>([]);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [validating, setValidating] = useState(false);
  const [resuggesting, setResuggesting] = useState(false);

  // ── Bootstrap : charge tout en parallèle + auto-suggest 1×/jour ──────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [slotsResp, ward, w, st, hist, rec] = await Promise.all([
          garderobeApi.getSlots(),
          garderobeApi.listVetements(),
          garderobeApi.getMeteo(),
          garderobeApi.stats(),
          garderobeApi.history(20),
          garderobeApi.recommendations(),
        ]);
        if (cancelled) return;
        setSlots(slotsResp.slots);
        setWardrobe(ward);
        setWeather(w);
        setStats(st);
        setHistory(hist);
        setRecs(rec);

        // Auto-suggest si pas encore fait aujourd'hui
        const last = typeof window !== "undefined" ? localStorage.getItem(LAST_SUGGESTION_KEY) : null;
        if (last !== todayKey()) {
          const sug = await garderobeApi.suggest();
          if (cancelled) return;
          applySuggestion(sug);
          if (typeof window !== "undefined") {
            localStorage.setItem(LAST_SUGGESTION_KEY, todayKey());
          }
        }
        setLoading(false);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message ?? "Erreur de chargement");
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applySuggestion = useCallback((sug: SuggestResponse) => {
    setSuggestion(sug);
    setUseBody(sug.use_body);
    const next: Record<string, Vetement | null> = {};
    for (const s of sug.slots) next[s.slot_id] = s.vetement;
    setTenue(next);
  }, []);

  const onResuggest = async () => {
    setResuggesting(true);
    try {
      const sug = await garderobeApi.suggest();
      applySuggestion(sug);
      localStorage.setItem(LAST_SUGGESTION_KEY, todayKey());
    } catch (e: any) {
      setError(e?.message ?? "Suggestion impossible");
    } finally {
      setResuggesting(false);
    }
  };

  const onReset = () => {
    const empty: Record<string, Vetement | null> = {};
    for (const s of slots) empty[s.id] = null;
    setTenue(empty);
    setUseBody(false);
  };

  const onValider = async () => {
    setValidating(true);
    try {
      const payload: Record<string, string | null> = {};
      for (const [sid, v] of Object.entries(tenue)) payload[sid] = v?.id ?? null;
      await garderobeApi.valider({ tenue: payload, use_body: useBody });
      // Refresh garde-robe + stats + history
      const [ward, st, hist] = await Promise.all([
        garderobeApi.listVetements(),
        garderobeApi.stats(),
        garderobeApi.history(20),
      ]);
      setWardrobe(ward);
      setStats(st);
      setHistory(hist);
      // Reset state pour le lendemain
      onReset();
      localStorage.removeItem(LAST_SUGGESTION_KEY);
    } catch (e: any) {
      setError(e?.message ?? "Validation impossible");
    } finally {
      setValidating(false);
    }
  };

  const slotsMap = useMemo(() => {
    const m: Record<string, SlotInfo> = {};
    for (const s of slots) m[s.id] = s;
    return m;
  }, [slots]);

  const wornItems = useMemo(() => Object.values(tenue).filter(Boolean) as Vetement[], [tenue]);

  // Calcul thermique côté front (cohérent avec /suggest, sans rappel API)
  const targetThermal = useMemo(() => {
    if (!weather) return 0;
    return 50 - 1.5 * weather.mean_window_temp;
  }, [weather]);

  const totalThermal = useMemo(() => {
    let total = wornItems.reduce((s, v) => s + v.thermal_score, 0);
    let layers = 0;
    if (tenue["Haut"]) layers++;
    if (tenue["Veste"]) layers++;
    if (tenue["Manteau"]) layers++;
    if (layers > 1) total *= 1 + (layers - 1) * 0.1;
    if (useBody) total += 1.5;
    return total;
  }, [tenue, useBody, wornItems]);

  if (loading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (error) {
    return <div className="p-6 text-[var(--destructive)]">⚠ {error}</div>;
  }

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Garde-robe</h1>
            <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Tenues &amp; météo</p>
          </div>
          <span className="text-xs rounded-md bg-[var(--muted)] px-2.5 py-1 text-[var(--muted-foreground)]">
            {wardrobe.length} pièces
          </span>
        </div>

        {weather && <WeatherBanner weather={weather} meanTemp={suggestion?.mean_temp ?? weather.mean_window_temp} />}

        <div className="flex gap-1 mt-4">
          {/* Tenue du jour — tab spéciale sans icône dans le tableau */}
          <button
            onClick={() => setTab("tenue")}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
              tab === "tenue"
                ? "text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
            }`}
          >
            <Shirt size={15} />Tenue du Jour
          </button>
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                tab === id
                  ? "text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
              }`}
            >
              <Icon size={15} />{label}
            </button>
          ))}
        </div>
      </div>

      <div key={tab} className="p-6 animate-fade-in-up">
        {tab === "tenue" && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 items-center">
              <button
                onClick={onResuggest}
                disabled={resuggesting}
                className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              >
                {resuggesting ? "…" : "✨ Re-suggérer"}
              </button>
              <button
                onClick={onReset}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)]"
              >
                🗑 Réinitialiser
              </button>
              <label className="ml-2 text-sm flex items-center gap-2">
                <input type="checkbox" checked={useBody} onChange={(e) => setUseBody(e.target.checked)} />
                👕 Body en coton (+1.5)
              </label>
            </div>

            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
              {SLOT_ROW_1.map((sid) => slotsMap[sid] && (
                <SlotCard
                  key={sid}
                  slot={slotsMap[sid]}
                  item={tenue[sid] ?? null}
                  candidates={wardrobe.filter((v) => slotsMap[sid].categories.includes(v.categorie))}
                  onChange={(next) => setTenue((t) => ({ ...t, [sid]: next }))}
                />
              ))}
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
              {SLOT_ROW_2.map((sid) => slotsMap[sid] && (
                <SlotCard
                  key={sid}
                  slot={slotsMap[sid]}
                  item={tenue[sid] ?? null}
                  candidates={wardrobe.filter((v) => slotsMap[sid].categories.includes(v.categorie))}
                  onChange={(next) => setTenue((t) => ({ ...t, [sid]: next }))}
                />
              ))}
            </div>

            <ThermalScore
              total={totalThermal}
              target={targetThermal}
              useBody={useBody}
              styleScore={suggestion?.style_score ?? 0}
            />

            <div className="flex justify-center">
              <button
                onClick={onValider}
                disabled={validating || wornItems.length === 0}
                className="rounded bg-[var(--success,#16a34a)] text-white px-6 py-2.5 text-sm font-semibold disabled:opacity-50"
              >
                {validating ? "…" : "✅ PORTER CETTE TENUE AUJOURD'HUI"}
              </button>
            </div>
          </div>
        )}

        {tab === "inventaire" && <InventaireTab wardrobe={wardrobe} />}
        {tab === "stats" && stats && <StatsTab stats={stats} />}
        {tab === "history" && <HistoriqueTab history={history} />}
        {tab === "recs" && <RecommandationsTab recs={recs} />}
      </div>
    </div>
  );
}
