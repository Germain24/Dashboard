import { Entrainement } from "@/components/entrainement/Entrainement";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function EntrainementPage() {
  return (
    <ErrorBoundary label="Entraînement">
      <Entrainement />
    </ErrorBoundary>
  );
}
