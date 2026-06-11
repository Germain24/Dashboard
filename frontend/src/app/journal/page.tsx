import Journal from "@/components/journal/Journal";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Journal — Mission Control" };

export default function JournalPage() {
  return (
    <ErrorBoundary label="Journal">
      <Journal />
    </ErrorBoundary>
  );
}
