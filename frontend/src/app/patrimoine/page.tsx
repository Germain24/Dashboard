import { PatrimoineTab } from "@/components/finance/PatrimoineTab";
import { ModuleHeader } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Patrimoine — Mission Control" };

export default function PatrimoinePage() {
  return (
    <div className="animate-fade-in">
      <ModuleHeader title="Patrimoine net" subtitle="Tes comptes en devise locale, total converti en €" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Patrimoine">
          <PatrimoineTab />
        </ErrorBoundary>
      </div>
    </div>
  );
}
