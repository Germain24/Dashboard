"use client";

import type { MonthTrend } from "@/lib/budget";
import {
  BudgetCharts,
  BudgetIntegrations,
  BudgetLoadingState,
  BudgetOverview,
} from "./BudgetMonthSections";
import CashflowSankey from "./CashflowSankey";
import InvestmentFlowsSummary from "./InvestmentFlowsSummary";
import { useBudgetMonthData } from "./useBudgetMonthData";

function monthOverMonth(trend: MonthTrend[]): number | null {
  const lastTwo = trend.slice(-2);
  if (lastTwo.length !== 2 || lastTwo[0].depenses <= 0) return null;
  return Math.round(((lastTwo[1].depenses - lastTwo[0].depenses) / lastTwo[0].depenses) * 100);
}

export default function MoisTab() {
  const data = useBudgetMonthData();
  if (data.isLoading) return <BudgetLoadingState />;
  const over = data.envelopes.filter((envelope) => envelope.status === "over");
  const warn = data.envelopes.filter((envelope) => envelope.status === "warning");
  return (
    <div className="space-y-6">
      <CashflowSankey />
      <InvestmentFlowsSummary />
      <BudgetOverview
        rolling={data.rolling}
        savings={data.savings}
        over={over}
        warn={warn}
        categoryName={data.categoryName}
        goalInput={data.goalInput}
        onGoalInput={data.setGoalInput}
        onSave={data.saveGoal}
      />
      <BudgetCharts
        periodMonths={data.periodMonths}
        onPeriodChange={data.setPeriodMonths}
        categoryShare={data.categoryShare}
        trend={data.trend}
        momPct={monthOverMonth(data.trend)}
        forecast={data.forecast}
        revenusDeltaPct={data.revenusDeltaPct}
        depensesDeltaPct={data.depensesDeltaPct}
        onRevenusChange={data.setRevenusDeltaPct}
        onDepensesChange={data.setDepensesDeltaPct}
        byTag={data.byTag}
      />
      <BudgetIntegrations
        month={data.month}
        groceryCost={data.groceryCost}
        reste={data.rolling.solde}
        recurring={data.recurring}
        projection={data.projection}
        alerts={data.alerts}
        envelopes={data.envelopes}
        categoryName={data.categoryName}
      />
    </div>
  );
}
