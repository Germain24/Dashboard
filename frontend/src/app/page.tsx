import { HealthBadge } from "@/components/HealthBadge";
import { Greeting } from "@/components/Greeting";
import { TodayPanel } from "@/components/home/TodayPanel";
import { Deck } from "@/components/layout";

export default function HomePage() {
  return (
    <Deck
      intro={
        <div className="animate-fade-in-up">
          <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <Greeting />
            <HealthBadge />
          </header>
          <TodayPanel />
        </div>
      }
    />
  );
}
