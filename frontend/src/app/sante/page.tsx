import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function SantePage() {
  const m = MODULES.find((x) => x.slug === "sante")!;
  return <ModulePlaceholder module={m} />;
}
