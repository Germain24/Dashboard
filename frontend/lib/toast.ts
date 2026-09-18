/**
 * Helpers de notification (toasts sonner) — point d'entrée unique.
 *
 * Pour les erreurs de query/mutation TanStack, le toast est automatique
 * (voir QueryProvider). Ces helpers servent au code impératif (handlers,
 * succès explicites).
 */

import { toast } from "sonner";

export { toast };

export function notifyError(error: unknown, fallback = "Une erreur est survenue"): void {
  const msg = error instanceof Error ? error.message : fallback;
  toast.error(msg);
}

export function notifySuccess(message: string): void {
  toast.success(message);
}
