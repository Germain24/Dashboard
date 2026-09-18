"use client";

import { useLifeGoals, useLifeGoalMetrics, useCreateLifeGoal, useDeleteLifeGoal } from "@/lib/queries/routines";
import { LifeGoalsSection, useLifeGoalForm } from "@/components/ObjectifsVieParts";

/** Objectifs de vie inter-modules (#226) + jalons datés (§5.4). */
export function ObjectifsVie() {
  const { data: goals } = useLifeGoals();
  const { data: metrics } = useLifeGoalMetrics();
  const create = useCreateLifeGoal();
  const del = useDeleteLifeGoal();
  const form = useLifeGoalForm(metrics, create);
  return <LifeGoalsSection goals={goals} del={del} form={form} />;
}
