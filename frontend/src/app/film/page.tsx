import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { moduleForSlug } from "@/lib/modules";

export default function FilmPage() {
  const m = moduleForSlug("film");
  return m ? <ModulePlaceholder module={m} /> : null;
}
