import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function GarderobePage() {
  const m = MODULES.find((x) => x.slug === "garderobe")!;
  return <ModulePlaceholder module={m} />;
}
