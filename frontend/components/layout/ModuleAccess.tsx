"use client";

import { useCallback, useEffect, useId, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clock3, Grid2X2, Search, Star, X } from "lucide-react";
import { GROUP_LABELS, MODULE_GROUPS, moduleForSlug } from "@/lib/modules";
import { cn } from "@/lib/utils";
import { Dialog, DialogBody, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const FAVORITES_KEY = "mc:module-favorites:v1";
const RECENTS_KEY = "mc:module-recents:v1";
const MIGRATION_KEY = "mc:module-access-server-migrated:v1";
const MAX_RECENTS = 6;

type ModuleAccessData = { favorites: string[]; recents: string[] };
type SyncStatus = "loading" | "online" | "offline" | "saving";
type ModuleAccessSnapshot = ModuleAccessData & { syncStatus: SyncStatus };

const EMPTY_ACCESS: ModuleAccessData = { favorites: [], recents: [] };
const SERVER_SNAPSHOT: ModuleAccessSnapshot = { ...EMPTY_ACCESS, syncStatus: "loading" };
let snapshot = SERVER_SNAPSHOT;
let mutationRevision = 0;
let syncPromise: Promise<void> | null = null;
let writeQueue: Promise<void> = Promise.resolve();
let syncUsers = 0;
let stopSyncLifecycle: (() => void) | null = null;
const subscribers = new Set<() => void>();

function validSlugs(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [
    ...new Set(
      value.filter(
        (slug): slug is string => typeof slug === "string" && Boolean(moduleForSlug(slug)),
      ),
    ),
  ];
}

function parseAccess(value: unknown): ModuleAccessData {
  if (!value || typeof value !== "object") return EMPTY_ACCESS;
  const record = value as Record<string, unknown>;
  return {
    favorites: validSlugs(record.favorites),
    recents: validSlugs(record.recents).slice(0, MAX_RECENTS),
  };
}

function parseSlugs(raw: string | null): string[] {
  try {
    return validSlugs(JSON.parse(raw ?? "[]"));
  } catch {
    return [];
  }
}

function readLocalAccess(): ModuleAccessData {
  try {
    return {
      favorites: parseSlugs(window.localStorage.getItem(FAVORITES_KEY)),
      recents: parseSlugs(window.localStorage.getItem(RECENTS_KEY)).slice(0, MAX_RECENTS),
    };
  } catch {
    return EMPTY_ACCESS;
  }
}

function writeLocalAccess(access: ModuleAccessData) {
  try {
    window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(access.favorites));
    window.localStorage.setItem(RECENTS_KEY, JSON.stringify(access.recents));
  } catch {
    // L'état en mémoire continue de fonctionner si le navigateur bloque le stockage local.
  }
}

function sameAccess(a: ModuleAccessData, b: ModuleAccessData) {
  return (
    a.favorites.length === b.favorites.length &&
    a.recents.length === b.recents.length &&
    a.favorites.every((slug, index) => slug === b.favorites[index]) &&
    a.recents.every((slug, index) => slug === b.recents[index])
  );
}

function publishSnapshot(access: ModuleAccessData, syncStatus: SyncStatus) {
  if (snapshot.syncStatus === syncStatus && sameAccess(snapshot, access)) return;
  snapshot = { favorites: [...access.favorites], recents: [...access.recents], syncStatus };
  subscribers.forEach((subscriber) => subscriber());
}

function subscribe(callback: () => void) {
  subscribers.add(callback);
  return () => subscribers.delete(callback);
}

function getSnapshot() {
  return snapshot;
}

function hasAccessData(access: ModuleAccessData) {
  return access.favorites.length > 0 || access.recents.length > 0;
}

async function requestSettings(init?: RequestInit) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 5_000);
  try {
    const response = await fetch("/api/settings", {
      ...init,
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Settings API indisponible (${response.status}).`);
    return (await response.json()) as { preferences?: Record<string, unknown> };
  } finally {
    window.clearTimeout(timeout);
  }
}

async function writeServerAccess(access: ModuleAccessData): Promise<ModuleAccessData> {
  const result = await requestSettings({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ module_access: access }),
  });
  const preferences = result.preferences;
  if (!preferences || !Object.prototype.hasOwnProperty.call(preferences, "module_access")) {
    throw new Error("L’API ne prend pas encore en charge les préférences de navigation.");
  }
  return parseAccess(preferences.module_access);
}

async function synchronizeFromServer() {
  if (snapshot.syncStatus === "saving") return;
  if (syncPromise) return syncPromise;
  const initialLocal = readLocalAccess();
  const revision = mutationRevision;
  publishSnapshot(initialLocal, "loading");

  syncPromise = (async () => {
    try {
      const result = await requestSettings();
      const preferences = result.preferences;
      if (!preferences || !Object.prototype.hasOwnProperty.call(preferences, "module_access")) {
        throw new Error("L’API ne prend pas encore en charge les préférences de navigation.");
      }
      if (revision !== mutationRevision) return;

      const serverAccess = parseAccess(preferences.module_access);
      const migrationDone = window.localStorage.getItem(MIGRATION_KEY) === "1";
      if (!hasAccessData(serverAccess) && hasAccessData(initialLocal) && !migrationDone) {
        const migrated = await writeServerAccess(initialLocal);
        if (revision !== mutationRevision) return;
        window.localStorage.setItem(MIGRATION_KEY, "1");
        writeLocalAccess(migrated);
        publishSnapshot(migrated, "online");
        return;
      }

      window.localStorage.setItem(MIGRATION_KEY, "1");
      writeLocalAccess(serverAccess);
      publishSnapshot(serverAccess, "online");
    } catch {
      if (revision === mutationRevision) publishSnapshot(initialLocal, "offline");
    }
  })().finally(() => {
    syncPromise = null;
  });

  return syncPromise;
}

function saveAccess(access: ModuleAccessData) {
  const next = parseAccess(access);
  const revision = ++mutationRevision;
  writeLocalAccess(next);
  publishSnapshot(next, "saving");

  const write = async () => {
    if (revision !== mutationRevision) return;
    try {
      const saved = await writeServerAccess(next);
      if (revision !== mutationRevision) return;
      window.localStorage.setItem(MIGRATION_KEY, "1");
      writeLocalAccess(saved);
      publishSnapshot(saved, "online");
    } catch {
      if (revision === mutationRevision) publishSnapshot(next, "offline");
    }
  };

  writeQueue = writeQueue.then(write, write);
}

function activateSynchronization() {
  syncUsers += 1;
  if (syncUsers === 1) {
    const refresh = () => void synchronizeFromServer();
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key !== FAVORITES_KEY && event.key !== RECENTS_KEY && event.key !== null) return;
      if (snapshot.syncStatus === "offline") {
        const local = readLocalAccess();
        publishSnapshot(local, "offline");
      } else {
        refresh();
      }
    };
    const interval = window.setInterval(refresh, 60_000);
    window.addEventListener("focus", refresh);
    window.addEventListener("storage", onStorage);
    document.addEventListener("visibilitychange", onVisibilityChange);
    stopSyncLifecycle = () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("storage", onStorage);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      stopSyncLifecycle = null;
    };
    refresh();
  }
  return () => {
    syncUsers -= 1;
    if (syncUsers === 0) stopSyncLifecycle?.();
  };
}

function useModuleAccess() {
  const pathname = usePathname();
  const access = useSyncExternalStore(subscribe, getSnapshot, () => SERVER_SNAPSHOT);

  useEffect(() => activateSynchronization(), []);

  useEffect(() => {
    if (access.syncStatus === "loading") return;
    const slug = pathname?.split("/").filter(Boolean)[0];
    if (!slug || !moduleForSlug(slug)) return;
    const next = [slug, ...access.recents.filter((item) => item !== slug)].slice(0, MAX_RECENTS);
    if (next.some((item, index) => access.recents[index] !== item)) {
      saveAccess({ ...access, recents: next });
    }
  }, [access, pathname]);

  const toggleFavorite = useCallback((slug: string) => {
    if (snapshot.syncStatus === "loading") return;
    const current = snapshot.favorites;
    const next = current.includes(slug)
      ? current.filter((item) => item !== slug)
      : [...current, slug];
    saveAccess({ ...snapshot, favorites: next });
  }, []);

  return { ...access, toggleFavorite };
}

type ModuleAccessProps = { variant: "dock" | "home" };

export function ModuleAccess({ variant }: ModuleAccessProps) {
  const { favorites, recents, syncStatus, toggleFavorite } = useModuleAccess();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const dialogId = useId();

  const normalizedQuery = query.trim().toLocaleLowerCase("fr-CA");
  const groups = useMemo(() => {
    if (!normalizedQuery) return MODULE_GROUPS;
    return MODULE_GROUPS.map((group) => ({
      ...group,
      items: group.items.filter((module) =>
        `${module.label} ${module.description} ${module.group}`
          .toLocaleLowerCase("fr-CA")
          .includes(normalizedQuery),
      ),
    })).filter((group) => group.items.length > 0);
  }, [normalizedQuery]);

  const openManager = () => {
    setQuery("");
    setOpen(true);
  };

  return (
    <>
      {variant === "dock" ? (
        <button
          type="button"
          onClick={openManager}
          aria-label="Ouvrir les favoris et les modules récents"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={dialogId}
          title="Favoris et modules récents"
          className="springy flex h-10 w-10 items-center justify-center rounded-[var(--radius-full)] text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
        >
          <Grid2X2 className="h-5 w-5" aria-hidden="true" />
        </button>
      ) : (
        <section className="mt-4" aria-labelledby={`${dialogId}-heading`}>
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2
              id={`${dialogId}-heading`}
              className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/55"
            >
              Tes modules
            </h2>
            <button
              type="button"
              onClick={openManager}
              aria-haspopup="dialog"
              aria-expanded={open}
              aria-controls={dialogId}
              className="inline-flex min-h-11 items-center gap-1 rounded-md px-2 text-xs font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            >
              <Star className="h-3.5 w-3.5" aria-hidden="true" />
              Gérer
            </button>
          </div>
          <div className="space-y-2">
            <ModuleStrip
              label="Favoris"
              icon="favorite"
              slugs={favorites}
              emptyLabel="Épingle les pages que tu ouvres souvent."
            />
            <ModuleStrip
              label="Récents"
              icon="recent"
              slugs={recents.slice(0, 4)}
              emptyLabel="Tes pages visitées apparaîtront ici."
            />
          </div>
        </section>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} className="max-w-2xl">
        <div id={dialogId}>
          <DialogHeader onClose={() => setOpen(false)}>
            <DialogTitle>Accès rapide</DialogTitle>
            <p
              className="mt-1 text-sm text-[var(--muted-foreground)]"
              role="status"
              aria-live="polite"
            >
              {syncStatus === "loading"
                ? "Chargement des préférences…"
                : syncStatus === "saving"
                  ? "Synchronisation en cours…"
                  : syncStatus === "offline"
                    ? "Hors ligne : les changements restent enregistrés sur cet appareil."
                    : "Tes favoris et tes récents sont synchronisés entre tes appareils."}
            </p>
          </DialogHeader>
          <DialogBody className="space-y-5 pb-5">
            <label className="relative block">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]"
                aria-hidden="true"
              />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Chercher un module…"
                aria-label="Filtrer les modules"
                className="min-h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] pl-9 pr-3 text-sm text-[var(--foreground)] outline-none transition-colors placeholder:text-[var(--muted-foreground)] focus:border-[var(--ring)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--ring)_20%,transparent)]"
              />
            </label>

            {!normalizedQuery && (
              <div className="grid gap-4 sm:grid-cols-2">
                <ModuleGroupList
                  title="Favoris"
                  slugs={favorites}
                  emptyLabel="Aucun favori. Utilise l’étoile dans la liste ci-dessous."
                  onToggle={toggleFavorite}
                  onNavigate={() => setOpen(false)}
                />
                <ModuleGroupList
                  title="Récemment ouverts"
                  slugs={recents}
                  emptyLabel="Les modules consultés apparaîtront ici."
                  onToggle={toggleFavorite}
                  onNavigate={() => setOpen(false)}
                />
              </div>
            )}

            <div className="space-y-4">
              {groups.map((group) => (
                <section key={group.group} aria-label={group.group}>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                    {GROUP_LABELS[group.group]}
                  </h3>
                  <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                    {group.items.map((module) => {
                      const Icon = module.icon;
                      const favorite = favorites.includes(module.slug);
                      return (
                        <li
                          key={module.slug}
                          className="flex min-w-0 items-center gap-1 rounded-lg border border-transparent hover:border-[var(--border)] hover:bg-[var(--muted)]"
                        >
                          <Link
                            href={`/${module.slug}`}
                            onClick={() => setOpen(false)}
                            title={module.description}
                            className="flex min-h-11 min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                          >
                            <Icon
                              className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]"
                              aria-hidden="true"
                            />
                            <span className="truncate">{module.label}</span>
                          </Link>
                          <button
                            type="button"
                            onClick={() => toggleFavorite(module.slug)}
                            aria-label={
                              favorite
                                ? `Retirer ${module.label} des favoris`
                                : `Ajouter ${module.label} aux favoris`
                            }
                            aria-pressed={favorite}
                            disabled={syncStatus === "loading"}
                            title={favorite ? "Retirer des favoris" : "Ajouter aux favoris"}
                            className={cn(
                              "mr-1 grid h-11 w-11 shrink-0 place-items-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                              favorite
                                ? "text-amber-400 hover:bg-amber-400/10"
                                : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
                              syncStatus === "loading" && "cursor-wait opacity-50",
                            )}
                          >
                            <Star
                              className={cn("h-4 w-4", favorite && "fill-current")}
                              aria-hidden="true"
                            />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
              {groups.length === 0 && (
                <p className="rounded-lg border border-dashed border-[var(--border)] px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
                  Aucun module ne correspond à « {query} ».
                </p>
              )}
            </div>
          </DialogBody>
        </div>
      </Dialog>
    </>
  );
}

function ModuleStrip({
  label,
  icon,
  slugs,
  emptyLabel,
}: {
  label: string;
  icon: "favorite" | "recent";
  slugs: string[];
  emptyLabel: string;
}) {
  const Icon = icon === "favorite" ? Star : Clock3;
  return (
    <div>
      <p className="mb-1 flex items-center gap-1 text-[10px] font-medium text-white/50">
        <Icon className="h-3 w-3" aria-hidden="true" />
        {label}
      </p>
      {slugs.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {slugs.map((slug) => {
            const module = moduleForSlug(slug);
            if (!module) return null;
            const ModuleIcon = module.icon;
            return (
              <li key={slug}>
                <Link
                  href={`/${slug}`}
                  className="inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:border-white/20 hover:bg-white/[0.09] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                >
                  <ModuleIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span className="max-w-32 truncate">{module.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-xs text-white/45">{emptyLabel}</p>
      )}
    </div>
  );
}

function ModuleGroupList({
  title,
  slugs,
  emptyLabel,
  onToggle,
  onNavigate,
}: {
  title: string;
  slugs: string[];
  emptyLabel: string;
  onToggle: (slug: string) => void;
  onNavigate: () => void;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-[var(--border)] p-3" aria-label={title}>
      <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[var(--foreground)]">
        {title === "Favoris" ? (
          <Star className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />
        ) : (
          <Clock3 className="h-3.5 w-3.5 text-[var(--muted-foreground)]" aria-hidden="true" />
        )}
        {title}
      </h3>
      {slugs.length ? (
        <ul className="space-y-1">
          {slugs.map((slug) => {
            const module = moduleForSlug(slug);
            if (!module) return null;
            const Icon = module.icon;
            return (
              <li key={slug} className="flex min-w-0 items-center gap-1">
                <Link
                  href={`/${slug}`}
                  onClick={onNavigate}
                  className="flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-md px-2 text-sm text-[var(--foreground)] hover:bg-[var(--muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                >
                  <Icon
                    className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]"
                    aria-hidden="true"
                  />
                  <span className="truncate">{module.label}</span>
                </Link>
                {title === "Favoris" && (
                  <button
                    type="button"
                    onClick={() => onToggle(slug)}
                    aria-label={`Retirer ${module.label} des favoris`}
                    disabled={snapshot.syncStatus === "loading"}
                    className="grid h-11 w-11 shrink-0 place-items-center rounded-md text-amber-400 hover:bg-amber-400/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">{emptyLabel}</p>
      )}
    </section>
  );
}
