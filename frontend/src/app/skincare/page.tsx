import { Skincare } from "@/components/skincare/Skincare";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function SkincarePage() {
  return (
    <ErrorBoundary label="Skincare">
      <Skincare />
    </ErrorBoundary>
  );
}
