import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function AgendaPage() {
  const m = MODULES.find((x) => x.slug === "agenda")!;
  return <ModulePlaceholder module={m} />;
}
