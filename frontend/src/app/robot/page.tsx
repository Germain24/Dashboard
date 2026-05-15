import { ModulePlaceholder } from "@/components/ModulePlaceholder";
import { MODULES } from "@/lib/modules";

export default function RobotPage() {
  const m = MODULES.find((x) => x.slug === "robot")!;
  return <ModulePlaceholder module={m} />;
}
