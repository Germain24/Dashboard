"""Énumération du catalogue Super C depuis le sitemap e-commerce.

Une seule requête HTTP (`/sitemap-ecomm-fr.xml`, ~2,3 Mo) donne l'inventaire
complet : 7 266 pages produit, chacune portant dans son URL le rayon, le nom
« slugifié » et le code-barres (UPC). Aucun scraping, aucun navigateur.

    https://www.superc.ca/allees/<rayon>/<nom-du-produit>/p/<upc>

Pourquoi le sitemap plutôt que la recherche : le `robots.txt` de superc.ca
interdit `*/recherche` ainsi que les paramètres `*filter=*` et `*page=*` — soit
exactement le chemin qu'emprunte `.superc_scrape.mjs` aujourd'hui. Le sitemap,
lui, est publié pour être lu. Il ne porte pas les prix (d'où le scraper, qui
reste nécessaire), mais il donne le périmètre, et il le donne honnêtement.

Ce module est PUR côté analyse (`parse_sitemap`, `is_food`) ; seul
`fetch_sitemap` touche au réseau, et il est best-effort comme tout le pipeline
prix : une panne ne doit jamais casser une génération de fenêtre.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.superc.ca/sitemap-ecomm-fr.xml"

#: UA réaliste : superc.ca est derrière Cloudflare, qui refuse les clients nus.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
)

#: Rayons qui ne se mangent pas — écartés avant tout rattachement nutritionnel.
#: `bieres-et-vins` en fait partie : l'alcool a bien des calories, mais il n'a
#: rien à faire dans un panier optimisé pour la couverture en micronutriments.
NON_FOOD_RAYONS: frozenset[str] = frozenset({
    "entretien-menager-et-nettoyage",
    "soins-et-beaute",
    "pharmacie",
    "essentiels-pour-animaux",
    "billets-de-loterie",
    "bieres-et-vins",
    "maison-et-cuisine",
    "vetements",
    "jouets-et-jeux",
    "cartes-cadeaux",
})

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.DOTALL)
_PRODUCT_RE = re.compile(r"/allees/(?P<chemin>[^?#]+?)/p/(?P<upc>[0-9A-Za-z_-]+)/?$")


def _cache_path() -> Path:
    return settings.imports_dir / "Cuisine" / "superc_sitemap.json"


def deslugify(slug: str) -> str:
    """« boisson-d-amande-non-sucree » -> « boisson d amande non sucree ».

    Le sitemap ne porte que le slug : pas de marque, pas de format, pas
    d'accents. C'est une base de rattachement plus propre que le libellé
    commercial complet, qui mêle marque et contenance.
    """
    return re.sub(r"[-_]+", " ", slug).strip()


def parse_sitemap(xml: str) -> list[dict]:
    """[{upc, rayon, slug, nom, url}] pour chaque page produit du sitemap.

    Les entrées non-produit (pages de rayon, contenu éditorial) sont ignorées.
    Un même UPC n'apparaît qu'une fois : le sitemap liste parfois un produit
    sous plusieurs chemins.
    """
    out: list[dict] = []
    vus: set[str] = set()
    for url in _LOC_RE.findall(xml):
        match = _PRODUCT_RE.search(url)
        if match is None:
            continue
        upc = match.group("upc")
        if upc in vus:
            continue
        vus.add(upc)
        segments = [s for s in match.group("chemin").split("/") if s]
        if not segments:
            continue
        # Dernier segment = nom du produit ; premier = rayon. Entre les deux,
        # un sous-rayon existe parfois (~5 % des produits), sans usage ici.
        rayon = segments[0]
        slug = segments[-1]
        out.append({
            "upc": upc,
            "rayon": rayon,
            "slug": slug,
            "nom": deslugify(slug),
            "url": url,
        })
    return out


def is_food(entry: dict) -> bool:
    """Le produit relève-t-il d'un rayon alimentaire ?"""
    return entry.get("rayon") not in NON_FOOD_RAYONS


def food_entries(entries: Iterable[dict]) -> list[dict]:
    return [e for e in entries if is_food(e)]


def fetch_sitemap(timeout: float = 60.0) -> Optional[str]:
    """Télécharge le sitemap, ou None en cas d'échec (best-effort, jamais fatal)."""
    try:
        import httpx

        response = httpx.get(
            SITEMAP_URL, timeout=timeout, follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
        return response.text
    except Exception as exc:
        logger.warning("[superc_catalog] sitemap indisponible (%s)", exc)
        return None


def load_cached_entries() -> list[dict]:
    """Entrées du dernier sitemap enregistré, ou [] si absent/illisible."""
    path = _cache_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def save_entries(entries: list[dict], scraped_at: str) -> Path:
    """Écrit le cache du sitemap. `scraped_at` est fourni par l'appelant (les
    fonctions de ce module restent sans horloge, donc testables)."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"source": SITEMAP_URL, "scraped_at": scraped_at,
             "count": len(entries), "items": entries},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return path
