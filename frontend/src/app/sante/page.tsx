import { Sante } from "@/components/sante/Sante";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function SantePage() {
  return (
    <ErrorBoundary label="Santé">
      <Sante />
    </ErrorBoundary>
  );
}
