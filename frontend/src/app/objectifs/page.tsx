import { Objectifs } from "@/components/objectifs/Objectifs";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function ObjectifsPage() {
  return (
    <ErrorBoundary label="Objectifs">
      <Objectifs />
    </ErrorBoundary>
  );
}
