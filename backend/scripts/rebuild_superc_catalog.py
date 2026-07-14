"""Phase 3 « Super C unique » — reconstruit les prix d'`aliments.csv` sur les
prix Super C, de façon NON destructive.

Lit le cache Super C (`superc.json`) + le catalogue actuel, écrit :
  - `aliments.candidate.csv` : le catalogue avec les prix Super C (aliments
    matchés) et les aliments non vendus chez Super C RETIRÉS ;
  - `items_retires.txt` : la liste des aliments retirés (aucun match Super C).

Le vrai `aliments.csv` n'est JAMAIS écrasé : à toi de comparer puis de basculer
(`mv aliments.candidate.csv aliments.csv`) une fois le candidat validé.

⚠️ Le cache `superc.json` est *search-based* (best-effort) : renseigne d'abord
les termes de la semaine / relève manuellement avant de te fier au candidat.
Les aliments matchés dépendent entièrement de ce que le scrape a ramené.

Usage :
    python -m scripts.rebuild_superc_catalog [--cache PATH] [--csv PATH] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.services.sante.adonis_pricing import load_superc_cached_items
from app.services.sante.superc_catalog_rebuild import (
    catalog_price_overlay,
    plan_rebuild,
    rewrite_catalog_csv,
)


def _default_csv() -> Path:
    return settings.imports_dir / "Sante" / "tableur" / "aliments.csv"


def _load_cache_items(cache_path: Path | None) -> list[dict]:
    if cache_path is None:
        return load_superc_cached_items()
    if not cache_path.exists():
        return []
    return json.loads(cache_path.read_text(encoding="utf-8")).get("items", [])


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconstruit aliments.csv sur les prix Super C (non destructif).")
    ap.add_argument("--cache", type=Path, default=None, help="superc.json (défaut : cache imports)")
    ap.add_argument("--csv", type=Path, default=None, help="aliments.csv source")
    ap.add_argument("--out-dir", type=Path, default=None, help="dossier de sortie (défaut : à côté du CSV)")
    args = ap.parse_args()

    csv_path = args.csv or _default_csv()
    if not csv_path.exists():
        print(f"[rebuild] catalogue introuvable : {csv_path}")
        return 1
    out_dir = args.out_dir or csv_path.parent

    items = _load_cache_items(args.cache)
    if not items:
        print("[rebuild] cache Super C vide -> rien à reconstruire (lance d'abord le scrape).")
        return 1

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    catalog_items = lines[0].split(";")[1:] if lines else []

    overlay = catalog_price_overlay(items)
    matched, unmatched = plan_rebuild(catalog_items, overlay)
    new_lines = rewrite_catalog_csv(lines, matched, unmatched)

    candidate = out_dir / "aliments.candidate.csv"
    report = out_dir / "items_retires.txt"
    candidate.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    report.write_text(
        "Aliments retirés (aucun prix Super C matché) :\n"
        + "\n".join(f"- {name}" for name in unmatched)
        + f"\n\nMatchés (re-tarifés Super C) : {len(matched)} / {len(catalog_items)}\n",
        encoding="utf-8",
    )

    print(f"[rebuild] {len(matched)}/{len(catalog_items)} aliments re-tarifés Super C, "
          f"{len(unmatched)} retirés.")
    print(f"[rebuild] candidat  -> {candidate}")
    print(f"[rebuild] retirés   -> {report}")
    print("[rebuild] aliments.csv NON modifié. Compare puis bascule le candidat toi-même.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
