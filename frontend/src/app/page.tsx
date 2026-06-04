import { HealthBadge } from "@/components/HealthBadge";
import { Greeting } from "@/components/Greeting";
import { TodayPanel } from "@/components/home/TodayPanel";
import { DaySignals } from "@/components/home/DaySignals";

export default function HomePage() {
  return (
    <div className="px-6 py-6 lg:px-8 lg:py-8">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4 animate-fade-in">
        <Greeting />
        <HealthBadge />
      </header>

      <TodayPanel />
      <DaySignals />
    </div>
  );
}
