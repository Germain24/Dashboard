import { Voyage } from "@/components/voyage/Voyage";
import { ModuleHeader } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Voyage — Mission Control" };

export default function VoyagePage() {
  return (
    <div>
      <ModuleHeader title="Voyage" subtitle="Planifie ton prochain itinéraire" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Voyage">
          <Voyage />
        </ErrorBoundary>
      </div>
    </div>
  );
}
