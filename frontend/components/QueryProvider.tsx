"use client";

/**
 * Provider TanStack Query + gestion d'erreurs globale (toasts sonner)
 * + persistance localStorage (mode hors-ligne / stale-while-revalidate).
 *
 * - staleTime court : les données s'affichent immédiatement depuis le cache puis
 *   se revalident en arrière-plan (SWR).
 * - persistance localStorage : au rechargement (ou hors-ligne), le dernier cache
 *   connu est réhydraté avant le refetch.
 */

import { useState } from "react";
import {
  MutationCache,
  QueryCache,
  QueryClient,
} from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { Toaster, toast } from "sonner";

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Une erreur est survenue";
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error) => toast.error(errorMessage(error)),
        }),
        mutationCache: new MutationCache({
          onError: (error) => toast.error(errorMessage(error)),
        }),
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 24 * 60 * 60 * 1000, // 24 h : conserve le cache pour l'offline
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  const [persister] = useState(() =>
    typeof window !== "undefined"
      ? createSyncStoragePersister({ storage: window.localStorage, key: "mc-query-cache" })
      : undefined,
  );

  // Côté serveur (SSR), pas de persistance : rendu direct.
  if (!persister) {
    return (
      <>
        {children}
        <Toaster position="bottom-right" richColors closeButton />
      </>
    );
  }

  return (
    <PersistQueryClientProvider
      client={client}
      persistOptions={{ persister, maxAge: 24 * 60 * 60 * 1000 }}
    >
      {children}
      <Toaster position="bottom-right" richColors closeButton />
    </PersistQueryClientProvider>
  );
}
