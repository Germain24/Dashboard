import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function CuisinePage() {
  const m = MODULES.find((x) => x.slug === "cuisine")!;
  return <ModulePlaceholder module={m} />;
}
