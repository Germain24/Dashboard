"use client";

/**
 * Provider TanStack Query + gestion d'erreurs globale (toasts sonner).
 *
 * - staleTime court : les données s'affichent immédiatement depuis le cache puis
 *   se revalident en arrière-plan (SWR).
 * Les domaines Finance, Santé et Agenda contiennent des données privées: le cache
 * reste volontairement en mémoire et n'est jamais sérialisé dans localStorage.
 */

import { useEffect, useState } from "react";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import { RealtimeProvider } from "@/components/RealtimeProvider";

const LEGACY_PERSISTED_CACHE_KEY = "mc-query-cache";

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
            gcTime: 30 * 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  useEffect(() => {
    window.localStorage.removeItem(LEGACY_PERSISTED_CACHE_KEY);
  }, []);

  return (
    <QueryClientProvider client={client}>
      <RealtimeProvider>
        {children}
        <Toaster position="bottom-right" richColors closeButton />
      </RealtimeProvider>
    </QueryClientProvider>
  );
}
