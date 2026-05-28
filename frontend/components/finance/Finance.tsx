"use client";

import { useState } from "react";
import { TrendingUp } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { SuiviTab } from "./SuiviTab";
import { CompositionTab } from "./CompositionTab";
import { BuffettTab } from "./BuffettTab";
import { RebalancingTab } from "./RebalancingTab";
import { TransactionsTab } from "./TransactionsTab";

type Tab = "suivi" | "composition" | "buffett" | "rebalancing" | "transactions";

export function Finance() {
  const [tab, setTab] = useState<Tab>("suivi");

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <TrendingUp className="h-5 w-5 shrink-0" />
        <h1 className="text-xl font-semibold tracking-tight">Finance</h1>
        <Badge variant="outline" className="ml-auto">Portefeuille</Badge>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="suivi">📈 Suivi</TabsTrigger>
          <TabsTrigger value="composition">🗂 Composition</TabsTrigger>
          <TabsTrigger value="buffett">🧠 Buffett</TabsTrigger>
          <TabsTrigger value="rebalancing">⚖️ Rebalancing</TabsTrigger>
          <TabsTrigger value="transactions">💳 Transactions</TabsTrigger>
        </TabsList>

        <TabsContent value="suivi">
          <SuiviTab />
        </TabsContent>
        <TabsContent value="composition">
          <CompositionTab />
        </TabsContent>
        <TabsContent value="buffett">
          <BuffettTab />
        </TabsContent>
        <TabsContent value="rebalancing">
          <RebalancingTab />
        </TabsContent>
        <TabsContent value="transactions">
          <TransactionsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
