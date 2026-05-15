import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function LivresPage() {
  const m = MODULES.find((x) => x.slug === "livres")!;
  return <ModulePlaceholder module={m} />;
}
