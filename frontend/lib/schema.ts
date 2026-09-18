/**
 * Accès pratique aux types générés depuis l'OpenAPI (lib/types.ts).
 *
 * Régénérer : `make gen-types` (ou `npm run gen:types` avec le backend lancé).
 *
 * Usage dans un lib module ::
 *
 *   import type { Schema } from "@/lib/schema";
 *   type PositionOut = Schema<"PositionOut">;
 *
 * Permet de remplacer progressivement les interfaces écrites à la main par les
 * types dérivés du backend (source de vérité unique).
 */

import type { components } from "@/lib/types";

export type Schemas = components["schemas"];

/** Raccourci : `Schema<"PositionOut">`. */
export type Schema<K extends keyof Schemas> = Schemas[K];
