import { Langues } from "@/components/langues/Langues";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function LanguesPage() {
  return (
    <ErrorBoundary label="Langues">
      <Langues />
    </ErrorBoundary>
  );
}
