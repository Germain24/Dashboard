import { HealthBadge } from "@/components/HealthBadge";
import { ModuleCard } from "@/components/ModuleCard";
import { MODULES } from "@/lib/modules";

export default function HomePage() {
  return (
    <div>
      <header className="mb-8 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Mission Control</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Dashboard personnel — 11 modules pour piloter ta vie.
          </p>
        </div>
        <HealthBadge />
      </header>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Modules
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {MODULES.map((m) => (
            <ModuleCard key={m.slug} module={m} />
          ))}
        </div>
      </section>
    </div>
  );
}
