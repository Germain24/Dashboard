import Agenda from "@/components/agenda/Agenda";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Agenda — Mission Control" };

export default function AgendaPage() {
  return (
    <ErrorBoundary label="Agenda">
      <Agenda />
    </ErrorBoundary>
  );
}
