import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { moduleForSlug } from "@/lib/modules";

export default function MusiquePage() {
  const m = moduleForSlug("musique");
  return m ? <ModulePlaceholder module={m} /> : null;
}
