import { Garderobe } from "@/components/garderobe/Garderobe";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function GarderobePage() {
  return (
    <ErrorBoundary label="Garde-robe">
      <Garderobe />
    </ErrorBoundary>
  );
}
