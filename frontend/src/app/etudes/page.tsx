import { Etudes } from "@/components/etudes/Etudes";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function EtudesPage() {
  return (
    <ErrorBoundary label="Études">
      <Etudes />
    </ErrorBoundary>
  );
}
