import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function FinancePage() {
  const m = MODULES.find((x) => x.slug === "finance")!;
  return <ModulePlaceholder module={m} />;
}
