"use client";

import type { WindowPlanResponse } from "@/lib/sante";
import { ConsoDrawer } from "./ConsoDrawer";
import { WaterWidget } from "./WaterWidget";
import { SleepWidget } from "./SleepWidget";
import { NutritionQualityWidget } from "./NutritionQualityWidget";
import { WorkoutBurnWidget } from "./WorkoutBurnWidget";
import { EnergyBalanceAlert } from "./EnergyBalanceAlert";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { FenetreGenerateControls, FenetreGenerationStatus, FenetreWindowSections } from "./FenetreTabParts";
import { buildMacroSummary, findFenetreDay, macroBalance, useFenetreCart, useFenetreConsumption, useFenetreGeneration } from "./FenetreTabController";

type Props = {
  goal: { poids_cible?: number | null } | null;
  onSaveMesure: (m: { date: string; poids?: number }) => Promise<void>;
  lastWeight?: number | null;
};

export function FenetreTab({ onSaveMesure, lastWeight }: Props) {
  const generation = useFenetreGeneration(onSaveMesure, lastWeight);
  const consumption = useFenetreConsumption();
  const cart = useFenetreCart();
  return <FenetreTabView generation={generation} consumption={consumption} cart={cart} />;
}

function FenetreTabView({ generation, consumption, cart }: {
  generation: ReturnType<typeof useFenetreGeneration>;
  consumption: ReturnType<typeof useFenetreConsumption>;
  cart: ReturnType<typeof useFenetreCart>;
}) {
  const win = currentWindow(generation.fenetreQ.data);
  const macros = buildMacroSummary(win);
  const macroBalanceValue = currentMacroBalance(win, macros);
  const globalBalance = currentGlobalBalance(win, macroBalanceValue);
  const drawerDay = findFenetreDay(win, consumption.consoDrawerDate);
  return (
    <div className="space-y-6">
      <FenetreGenerateControls
        poids={generation.poids}
        generating={generation.generating}
        hasWindow={hasWindow(win)}
        onPoidsChange={generation.setPoids}
        onGenerate={(force, refresh) => void generation.onGenerate(force, refresh)}
      />
      <FenetreGenerationStatus job={generation.genJob} onStop={() => void generation.onStopGenerate()} />
      <DailyWidgets />
      <FenetreWindowSlot
        win={win}
        macros={macros}
        macroBalance={macroBalanceValue}
        globalBalance={globalBalance}
        consumption={consumption}
        cart={cart}
        cartPlan={generation.cartPlanQ.data}
      />
      <ConsoDrawer
        open={consumption.consoDrawerDate != null}
        onClose={() => consumption.setConsoDrawerDate(null)}
        planItems={dayItems(drawerDay)}
        initialConsumed={null}
        onSave={consumption.onSaveForDay}
      />
    </div>
  );
}

function currentWindow(value: WindowPlanResponse | undefined) { return value ?? null; }
function hasWindow(value: WindowPlanResponse | null) { return value !== null; }
function currentMacroBalance(win: WindowPlanResponse | null, macros: ReturnType<typeof buildMacroSummary>) {
  return win?.score.equilibre_macros ?? macroBalance(macros);
}
function currentGlobalBalance(win: WindowPlanResponse | null, macroValue: number) {
  return win?.score.equilibre_moyen ?? averageBalance(win, macroValue);
}
function averageBalance(win: WindowPlanResponse | null, macroValue: number) {
  return (coverageBalance(win) + macroValue) / 2;
}
function coverageBalance(win: WindowPlanResponse | null) { return win?.score.couverture_moyenne ?? 0; }
function dayItems(day: WindowPlanResponse["jours"][number] | null) { return day?.items ?? []; }

function DailyWidgets() {
  return (
    <CollapsibleSection title="Suivi quotidien" defaultOpen={false}>
      <div className="space-y-3"><div className="grid gap-3 sm:grid-cols-2"><WaterWidget /><SleepWidget /></div><EnergyBalanceAlert /><NutritionQualityWidget /><WorkoutBurnWidget /></div>
    </CollapsibleSection>
  );
}

function FenetreWindowSlot({ win, macros, macroBalance, globalBalance, consumption, cart, cartPlan }: {
  win: WindowPlanResponse | null;
  macros: ReturnType<typeof buildMacroSummary>;
  macroBalance: number;
  globalBalance: number;
  consumption: ReturnType<typeof useFenetreConsumption>;
  cart: ReturnType<typeof useFenetreCart>;
  cartPlan: ReturnType<typeof useFenetreGeneration>["cartPlanQ"]["data"];
}) {
  if (!win) return <p className="text-sm text-[var(--muted-foreground)]">Aucune fenêtre. Entre ton poids (lundi ou jeudi) puis « Générer ».</p>;
  return (
    <FenetreWindowSections
      win={win}
      macros={macros}
      macroBalance={macroBalance}
      globalBalance={globalBalance}
      checked={consumption.checked}
      savedDates={consumption.savedDates}
      savingDate={consumption.savingDate}
      consoError={consumption.consoErr}
      cartPlan={cartPlan}
      cartJob={cart.cartJob}
      cartPending={cart.cartPending}
      cartError={cart.cartError}
      onChecked={consumption.onChecked}
      onConsume={consumption.onConsume}
      onAdjust={consumption.setConsoDrawerDate}
      onStartCart={cart.onStartCart}
    />
  );
}
