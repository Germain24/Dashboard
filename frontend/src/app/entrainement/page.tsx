import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function EntrainementPage() {
  const m = MODULES.find((x) => x.slug === "entrainement")!;
  return <ModulePlaceholder module={m} />;
}
