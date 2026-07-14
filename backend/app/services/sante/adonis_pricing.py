"""Re-tarification des fruits & légumes du catalogue nutrition avec les prix Adonis.

L'utilisateur achète ses fruits & légumes chez Adonis (meilleure qualité), le
reste chez Costco. Le site groupeadonis.ca n'affiche pas de prix : on lit la
vitrine « Adonis powered by Instacart » via le scraper `frontend/.adonis_scrape.mjs`
(cache JSON), puis on remplace le `Prix` (CAD/100 g comestible) des SEULS fruits
& légumes dans le DataFrame du catalogue. Les valeurs nutritionnelles (CIQUAL)
sont conservées. Voir mémoire [[adonis-produce-scraper]].

Parties pures (matching, conversion, overlay) testées ; le rafraîchissement
(scrape navigateur) est best-effort et ne casse jamais l'optimisation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

def _cache_path() -> Path:
    """Cache des prix Adonis (écrit par le scraper). Gitignoré (data/imports/*).

    Résolu à l'appel (pas à l'import) pour respecter un `imports_dir`
    monkeypatché en test → cache absent → re-tarification neutre."""
    return settings.imports_dir / "Cuisine" / "adonis_fruits_legumes.json"

# Fractions comestibles (cf. README_aliments.md) : le prix Adonis est au poids
# BRUT (avec pelure/noyau) ; on le ramène à la portion comestible. 1.0 = tout
# comestible (baies, frozen, feuilles…).
_EDIBLE_DEFAULT = 1.0

# Fruits & légumes du catalogue (noms FR exacts d'aliments.csv) -> mots-clés de
# recherche dans le nom Adonis (anglais) + fraction comestible. `not` exclut les
# faux positifs (ex. "grape" ne doit pas matcher "grapefruit"/"grape tomato").
PRODUCE_MAP: dict[str, dict] = {
    "Banane": {"kw": ["banana"], "edible": 0.64},
    "Avocat": {"kw": ["avocado"], "edible": 0.73},
    "Orange": {"kw": ["orange"], "not": ["juice"], "edible": 0.73},
    "Pomme": {"kw": ["apple"], "edible": 0.90},
    "Raisins": {"kw": ["grape"], "not": ["grapefruit", "tomato"], "edible": 1.0},
    "Bleuets frais": {"kw": ["blueberr"], "edible": 1.0},
    "Fraises": {"kw": ["strawberr"], "edible": 1.0},
    "Framboises": {"kw": ["raspberr"], "edible": 1.0},
    "Cerises": {"kw": ["cherr"], "edible": 1.0},
    "Dattes Medjool": {"kw": ["medjool"], "edible": 0.85},
    "Ananas": {"kw": ["pineapple"], "edible": 1.0},
    "Kiwi": {"kw": ["kiwi"], "edible": 1.0},
    "Clementines": {"kw": ["clementine"], "edible": 0.73},
    "Poire": {"kw": ["pear"], "edible": 0.90},
    "Peche": {"kw": ["peach"], "edible": 0.90},
    "Mangue": {"kw": ["mango"], "edible": 1.0},
    "Grenade": {"kw": ["pomegranate"], "edible": 1.0},
    "Pamplemousse": {"kw": ["grapefruit"], "edible": 1.0},
    "Prunes": {"kw": ["plum"], "edible": 1.0},
    "Pruneaux": {"kw": ["prune"], "edible": 1.0},
    "Canneberges sechees": {"kw": ["cranberr"], "edible": 1.0},
    "Brocoli": {"kw": ["broccoli"], "edible": 1.0},
    "Epinards": {"kw": ["spinach"], "edible": 1.0},
    "Carottes": {"kw": ["carrot"], "edible": 0.89},
    # Adonis liste surtout des poivrons jaune/orange au même prix ($/kg) ; on
    # accepte n'importe quel poivron (bell pepper) comme proxy du poivron rouge.
    "Poivron rouge": {"kw": ["bell", "pepper"], "edible": 0.82},
    "Oignon": {"kw": ["onion"], "edible": 0.90},
    "Tomate fraiche": {"kw": ["tomato"], "edible": 1.0},
    "Patate douce": {"kw": ["sweet potato"], "edible": 0.86},
    "Champignons blancs": {"kw": ["mushroom"], "edible": 1.0},
    "Chou-fleur": {"kw": ["cauliflower"], "edible": 1.0},
    "Concombre": {"kw": ["cucumber"], "edible": 1.0},
    "Celeri": {"kw": ["celery"], "edible": 1.0},
    "Asperges": {"kw": ["asparagus"], "edible": 1.0},
    "Courgette": {"kw": ["zucchini"], "edible": 1.0},
    "Aubergine": {"kw": ["eggplant"], "edible": 1.0},
    "Roquette": {"kw": ["arugula"], "edible": 1.0},
    "Haricots verts": {"kw": ["green bean"], "edible": 1.0},
    "Pois verts surgeles": {"kw": ["green pea"], "edible": 1.0},
    "Olives noires": {"kw": ["black olive"], "edible": 1.0},
}

_LB_KG = 0.453592
_OZ_KG = 0.0283495


def _unit_to_kg(v: float, u: str) -> float | None:
    """Convertit `v` d'unité `u` en kg. Le volume (ml/l) suppose une densité ≈
    1 g/ml (eau/lait/sirop/conserves liquides) — approximation raisonnable pour
    un candidat à revoir, sinon impossible de tarifer les produits en ml/L."""
    return {
        "kg": v, "g": v / 1000, "lb": v * _LB_KG, "oz": v * _OZ_KG,
        "ml": v / 1000, "l": v,
    }.get(u)


def _format_weight_kg(item: dict) -> float | None:
    """Poids (kg) déduit du format ("675 g", "1.75 kg", "540 ml", "2 l") ou, à
    défaut, du slug d'URL ("blackberries-6-oz", "gala-apple-3-lbs", "...-1-75-kg").
    Le volume (ml/l) est ramené au poids via densité ≈ 1 (cf. `_unit_to_kg`)."""
    m = re.search(r"([\d.]+)\s*(kg|g|lb|oz|ml|l)\b", item.get("format") or "", re.I)
    if m:
        return _unit_to_kg(float(m.group(1)), m.group(2).lower())
    # Slug : "-6-oz", "-675-g", "-3-lbs", "-1-75-kg" (le point devient tiret).
    h = re.search(r"-(\d+(?:-\d+)?)-(kg|g|lbs?|oz|ml|l)(?:[-?/]|$)", item.get("href") or "", re.I)
    if h:
        v = float(h.group(1).replace("-", "."))
        return _unit_to_kg(v, h.group(2).lower().rstrip("s"))
    return None


def adonis_price_per_100g_edible(item: dict, edible: float = _EDIBLE_DEFAULT) -> float | None:
    """CAD/100 g de portion comestible depuis un item Adonis, ou None si indéterminable.

    Priorité au prix unitaire au poids ($/kg ou $/lb) ; sinon dérivé du prix
    paquet + poids du format.
    """
    edible = edible or 1.0
    per_kg = None
    up, u = item.get("unit_price"), (item.get("unit") or "").lower()
    if up and u:
        if u == "kg":
            per_kg = up
        elif u == "lb":
            per_kg = up / _LB_KG
        elif u == "g":
            per_kg = up * 1000
    if per_kg is None and item.get("price"):
        w = _format_weight_kg(item)
        if w:
            per_kg = item["price"] / w
    if per_kg is None:
        return None
    return round((per_kg / 10.0) / edible, 3)


def _matches(item: dict, spec: dict) -> bool:
    # On cherche dans le nom ET le slug d'URL (le nom img est parfois un nom de
    # marchand peu fiable ; le slug porte l'identité réelle du produit).
    # `match` = "all" (défaut) : tous les mots-clés requis (ex. bell+pepper) ;
    # "any" : au moins un (mots-clés SYNONYMES, ex. ground beef / extra lean beef).
    n = (str(item.get("name") or "") + " " + str(item.get("href") or "")).lower()
    kws = spec["kw"]
    if spec.get("match", "all") == "any":
        if not any(re.search(r"\b" + re.escape(kw), n) for kw in kws):
            return False
    elif any(not re.search(r"\b" + re.escape(kw), n) for kw in kws):
        return False
    return not any(re.search(r"\b" + re.escape(no), n) for no in spec.get("not", []))


def build_price_overlay(adonis_items: list[dict], item_map: dict | None = None) -> dict[str, float]:
    """{aliment FR: prix CAD/100 g comestible} pour les aliments matchés.

    `item_map` (défaut : PRODUCE_MAP, les fruits & légumes) mappe chaque aliment
    FR à `{kw, edible, not?}`. Passer un autre map (ex. CATALOG_MAP) pour couvrir
    tout le catalogue. En cas de plusieurs correspondances, garde la MOINS chère.
    """
    if item_map is None:
        item_map = PRODUCE_MAP
    overlay: dict[str, float] = {}
    for fr, spec in item_map.items():
        best = None
        for it in adonis_items:
            if not (it.get("name") or it.get("href")) or not _matches(it, spec):
                continue
            p = adonis_price_per_100g_edible(it, spec.get("edible", _EDIBLE_DEFAULT))
            if p is not None and (best is None or p < best):
                best = p
        if best is not None:
            overlay[fr] = best
    return overlay


def apply_overlay_to_df(df, overlay: dict[str, float]):
    """Remplace `Prix` des aliments présents dans `overlay` ET dans `df`.

    Retourne (df, liste des aliments effectivement re-tarifés)."""
    changed = []
    for nom, prix in overlay.items():
        if nom in df.index:
            df.loc[nom, "Prix"] = prix
            changed.append(nom)
    return df, changed


# ── Orchestration (best-effort, jamais bloquant pour l'optimisation) ──────────

def load_cached_items() -> list[dict]:
    path = _cache_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def _cache_age_seconds() -> float:
    try:
        return time.time() - _cache_path().stat().st_mtime
    except OSError:
        return float("inf")


def refresh_if_stale(max_age_h: float) -> bool:
    """Relance le scraper Adonis si le cache est trop vieux. True si rafraîchi.

    Best-effort : node/Edge/réseau absents ou scrape en échec -> on garde le cache.
    """
    if _cache_age_seconds() < max_age_h * 3600:
        return False
    repo_root = settings.data_dir.parent
    script = repo_root / "frontend" / ".adonis_scrape.mjs"
    if not script.exists():
        return False
    try:
        subprocess.run(
            ["node", script.name, str(_cache_path())],
            cwd=str(script.parent),
            timeout=float(os.getenv("ADONIS_SCRAPE_TIMEOUT_SEC", "150")),
            capture_output=True,
        )
        return True
    except Exception as exc:  # FileNotFoundError (node absent), TimeoutExpired…
        logger.warning("[adonis] scrape échoué (%s) — prix en cache conservés", exc)
        return False


def apply_adonis_produce_prices(df, *, refresh: bool = True):
    """Re-tarife les fruits & légumes du DataFrame catalogue avec les prix Adonis.

    `refresh=True` rafraîchit d'abord le cache si périmé (au lancement de
    l'optimisation). Best-effort : toute erreur laisse `df` inchangé.
    Retourne (df, liste des aliments re-tarifés).
    """
    if os.getenv("ADONIS_PRODUCE_PRICING", "1") not in ("1", "true", "True"):
        return df, []
    try:
        if refresh:
            refresh_if_stale(float(os.getenv("ADONIS_SCRAPE_MAX_AGE_H", "12")))
        items = load_cached_items()
        if not items:
            return df, []
        return apply_overlay_to_df(df, build_price_overlay(items))
    except Exception as exc:
        logger.warning("[adonis] re-tarification ignorée (%s)", exc)
        return df, []


# ── Super C (magasin unique, Phase 2 « Super C unique ») ──────────────────────
# Le cache superc.json est du même schéma Instacart qu'Adonis (écrit par
# frontend/.superc_scrape.mjs via store_pricing.refresh_all_if_stale au
# démarrage), donc build_price_overlay / adonis_price_per_100g_edible sont
# réutilisés tels quels : seule la source du cache change.
# NOTE Phase 3 : renommer ce module (produce_pricing) et retirer le volet Adonis.

def _superc_cache_path() -> Path:
    return settings.imports_dir / "Cuisine" / "superc.json"


def load_superc_cached_items() -> list[dict]:
    path = _superc_cache_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def apply_superc_produce_prices(df):
    """Re-tarife les fruits & légumes du catalogue avec les prix Super C.

    Best-effort : cache absent/illisible ou toute erreur -> `df` inchangé. La
    fraîcheur du cache superc.json est assurée par
    `store_pricing.refresh_all_if_stale` au démarrage (scrape search-based sur
    les termes de la semaine) — pas de scrape à la volée ici. Désactivable via
    SUPERC_PRODUCE_PRICING=0. Retourne (df, liste des aliments re-tarifés).
    """
    if os.getenv("SUPERC_PRODUCE_PRICING", "1") not in ("1", "true", "True"):
        return df, []
    try:
        items = load_superc_cached_items()
        if not items:
            return df, []
        return apply_overlay_to_df(df, build_price_overlay(items))
    except Exception as exc:
        logger.warning("[superc] re-tarification produce ignorée (%s)", exc)
        return df, []
