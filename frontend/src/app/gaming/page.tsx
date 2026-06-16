import { Gaming } from "@/components/gaming/Gaming";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function GamingPage() {
  return (
    <ErrorBoundary label="Gaming">
      <Gaming />
    </ErrorBoundary>
  );
}
