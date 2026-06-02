/**
 * Internationalisation légère par dictionnaire (fr-CA par défaut).
 *
 * Pas de dépendance : un dictionnaire plat + une fonction `t(clé, vars?)`.
 * Pour ajouter une langue, dupliquer le dictionnaire et changer `LOCALE`.
 *
 * Usage : t("common.save") · t("finance.positions", { n: 3 })
 */

export type Locale = "fr-CA";

export const LOCALE: Locale = "fr-CA";

type Dict = Record<string, string>;

const fr_CA: Dict = {
  "common.save": "Enregistrer",
  "common.cancel": "Annuler",
  "common.delete": "Supprimer",
  "common.edit": "Modifier",
  "common.add": "Ajouter",
  "common.loading": "Chargement…",
  "common.error": "Une erreur est survenue",
  "common.empty": "Aucune donnée",
  "common.retry": "Réessayer",
  "common.search": "Rechercher…",
  "common.today": "Aujourd'hui",
  "common.week": "Semaine",
  "nav.finance": "Finance",
  "nav.sante": "Santé",
  "nav.agenda": "Agenda",
  "nav.etudes": "Études",
  "nav.entrainement": "Entraînement",
  "nav.budget": "Budget",
  "nav.cuisine": "Cuisine",
  "nav.habitudes": "Habitudes",
  "nav.livres": "Livres",
  "nav.garderobe": "Garde-robe",
  "finance.positions": "{n} positions",
};

const DICTS: Record<Locale, Dict> = { "fr-CA": fr_CA };

/** Traduit une clé. Interpole `{var}` depuis `vars`. Renvoie la clé si absente. */
export function t(key: string, vars?: Record<string, string | number>): string {
  const dict = DICTS[LOCALE];
  let str = dict[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return str;
}
