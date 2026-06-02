/**
 * Validation des variables d'environnement publiques (zod).
 *
 * Échoue tôt (au build / au premier import) si la config est invalide.
 * En production, NEXT_PUBLIC_API_BASE_URL est requis ; en dev il a un défaut.
 *
 * Next.js inline les variables NEXT_PUBLIC_* au build : on les référence
 * littéralement pour que le remplacement statique fonctionne.
 */

import { z } from "zod";

const isProd = process.env.NODE_ENV === "production";

const schema = z.object({
  NEXT_PUBLIC_API_BASE_URL: isProd
    ? z.string().url({ message: "NEXT_PUBLIC_API_BASE_URL doit être une URL valide en production" })
    : z.string().url().optional().default("http://127.0.0.1:8000"),
  NEXT_PUBLIC_API_PREFIX: z.string().optional().default("/api/v1"),
});

const parsed = schema.safeParse({
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_API_PREFIX: process.env.NEXT_PUBLIC_API_PREFIX,
});

if (!parsed.success) {
  const issues = parsed.error.issues.map((i) => `  - ${i.path.join(".")}: ${i.message}`).join("\n");
  throw new Error(`Configuration d'environnement invalide :\n${issues}`);
}

export const env = parsed.data;
