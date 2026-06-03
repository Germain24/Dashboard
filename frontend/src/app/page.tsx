import { HealthBadge } from "@/components/HealthBadge";
import { Greeting } from "@/components/Greeting";
import { SortableModules } from "@/components/SortableModules";
import { TodayAgenda } from "@/components/TodayAgenda";
import { MODULES } from "@/lib/modules";

export default function HomePage() {
  const readyCount = MODULES.filter((m) => m.ready).length;
  const totalCount = MODULES.length;

  return (
    <div className="px-6 py-6 lg:px-8 lg:py-8">
      <header className="mb-8 animate-fade-in">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <Greeting />
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              {readyCount} module{readyCount > 1 ? "s" : ""} actif{readyCount > 1 ? "s" : ""}
              {" "}&middot;{" "}
              {totalCount - readyCount} à venir
            </p>
          </div>
          <HealthBadge />
        </div>

        <div
          className="mt-4 flex items-center gap-3"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={totalCount}
          aria-valuenow={readyCount}
          aria-label={readyCount + " modules sur " + totalCount + " livrés"}
        >
          <div className="h-1 flex-1 rounded-full overflow-hidden bg-[var(--border)]">
            <div
              className="h-full rounded-full bg-[var(--ring)] transition-all duration-300"
              style={{ width: ((readyCount / totalCount) * 100) + "%" }}
            />
          </div>
          <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
            {readyCount}/{totalCount}
          </span>
        </div>
      </header>

      <TodayAgenda />

      <section aria-label="Modules">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-widest text-[var(--muted-foreground)]">
          Modules <span className="ml-1 font-normal normal-case tracking-normal opacity-70">— glisse pour réorganiser</span>
        </h2>
        <SortableModules />
      </section>
    </div>
  );
}
