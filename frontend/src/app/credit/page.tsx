import { CreditTab } from "@/components/finance/CreditTab";
import { ModuleHeader } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Marge de crédit — Mission Control" };

export default function CreditPage() {
  return (
    <div>
      <ModuleHeader title="Marge de crédit" subtitle="Feuille de route pour maximiser ta marge de crédit totale" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Marge de crédit">
          <CreditTab />
        </ErrorBoundary>
      </div>
    </div>
  );
}
