import { Finance } from "@/components/finance/Finance";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function FinancePage() {
  return (
    <ErrorBoundary label="Finance">
      <Finance />
    </ErrorBoundary>
  );
}
