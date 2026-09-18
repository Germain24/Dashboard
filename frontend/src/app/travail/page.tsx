import { Travail } from "@/components/travail/Travail";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function TravailPage() {
  return (
    <ErrorBoundary label="Travail">
      <Travail />
    </ErrorBoundary>
  );
}
