"use client";

/**
 * Micro-feedback de succès : un checkmark animé qui apparaît brièvement
 * après une mutation réussie (usage inline). Le feedback global passe par les
 * toasts sonner (voir lib/toast.ts notifySuccess) ; ce composant sert aux
 * confirmations inline (à côté d'un bouton/champ).
 *
 * Usage :
 *   const [ok, setOk] = useState(false);
 *   // après succès : setOk(true)
 *   {ok && <SuccessCheck onDone={() => setOk(false)} />}
 */

import { useEffect } from "react";
import { Check } from "lucide-react";

export function SuccessCheck({ onDone, durationMs = 1500 }: { onDone?: () => void; durationMs?: number }) {
  useEffect(() => {
    if (!onDone) return;
    const id = setTimeout(onDone, durationMs);
    return () => clearTimeout(id);
  }, [onDone, durationMs]);

  return (
    <span
      role="status"
      aria-label="Succès"
      className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-[color-mix(in_srgb,var(--success)_18%,transparent)] text-[var(--success)] animate-scale-in"
    >
      <Check size={13} />
    </span>
  );
}
