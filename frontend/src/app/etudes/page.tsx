import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function EtudesPage() {
  const m = MODULES.find((x) => x.slug === "etudes")!;
  return <ModulePlaceholder module={m} />;
}
