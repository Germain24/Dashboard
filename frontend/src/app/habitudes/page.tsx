import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function HabitudesPage() {
  const m = MODULES.find((x) => x.slug === "habitudes")!;
  return <ModulePlaceholder module={m} />;
}
