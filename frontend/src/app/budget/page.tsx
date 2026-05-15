import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function BudgetPage() {
  const m = MODULES.find((x) => x.slug === "budget")!;
  return <ModulePlaceholder module={m} />;
}
