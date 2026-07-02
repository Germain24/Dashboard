import { Voyage } from "@/components/voyage/Voyage";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function VoyagePage() {
  return (
    <ErrorBoundary label="Voyage">
      <Voyage />
    </ErrorBoundary>
  );
}
