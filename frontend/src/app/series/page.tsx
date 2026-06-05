import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { moduleForSlug } from "@/lib/modules";

export default function SeriesPage() {
  const m = moduleForSlug("series");
  return m ? <ModulePlaceholder module={m} /> : null;
}
