"""Import de l'inventaire garde-robe depuis le dossier géré à la main.

Source (`settings.garderobe_inventaire_dir`, .env: GARDEROBE_INVENTAIRE_DIR) :
    Vetements.xlsx        feuille 0 : 1 ligne = 1 pièce
        Marque | Type | Couleur | Couleur Secondaire | Motifs |
        Photos Avant | Photos Arriere | Photos Pixelise | Usure | <matières...>
    Pixelisé/<Dossier>/*.png   pixel arts (rangés librement par l'utilisateur)
    Normal/*.jpg               photos avant/arrière

Ce que fait l'import (idempotent, relançable à chaque mise à jour du dossier) :
  1. copie les pixel arts vers frontend/public/garderobe/assets/<Cat>/ --
     les fichiers déjà en slug gardent leur nom (la DB les référence déjà),
     les fichiers numérotés (Veste01.png...) sont renommés en
     <type>-<marque>-<couleur>.png d'après leur ligne Excel ;
  2. copie les photos avant/arrière vers data/garderobe_photos/ ;
  3. upsert des pièces en base :
     - pièce EXISTANTE (même pixel art) : ne touche PAS aux champs curés
       (nom, couleur, catégorie...), met à jour image/extra/type_objectif --
       l'Excel n'est pas encore vérifié (dixit l'utilisateur), la base l'est ;
     - pièce NOUVELLE : créée entièrement depuis l'Excel (id = slug,
       extra.a_verifier = true).

La CATÉGORIE (qui pilote le slot thermique : Manteau = froid/pluie, Veste =
frais, cf. constants.SLOTS) vient du TYPE de la pièce, pas du dossier où vit
le pixel art (tous les extérieurs sont rangés dans Pixelisé/Manteau/).
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.models.garderobe import ObjectifType, Vetement
from app.services.garderobe.photos import MEDIA_URL_PREFIX, photos_dir

REPO_ROOT = Path(__file__).resolve().parents[4]
ASSETS_DIR = REPO_ROOT / "frontend" / "public" / "garderobe" / "assets"


def inventaire_dir() -> Path:
    return Path(settings.garderobe_inventaire_dir)


# ── Slugs (même convention que scripts/reorg_garderobe_assets) ───────────────

def slugify(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()


def build_slug(type_: str | None, marque: str | None, couleur: str | None) -> str:
    parts = [p for p in (slugify(type_), slugify(marque), slugify(couleur)) if p]
    return "-".join(parts) or "sans-nom"


# ── Normalisation des couleurs ───────────────────────────────────────────────
# L'app attend la casse "Bleu marine" (cf. constants.NEUTRES/SECONDAIRES/
# ACCENTS) ; l'Excel écrit "Bleu Marine". Les couleurs inédites reçoivent une
# forme canonique cohérente (1re lettre en majuscule seulement).

def _canonical_colors() -> list[str]:
    from app.services.garderobe.constants import ACCENTS, NEUTRES, SECONDAIRES
    return list(NEUTRES) + list(SECONDAIRES) + list(ACCENTS)


def _norm_txt(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def normalize_couleur(raw: str | None) -> str | None:
    """'Bleu Marine' -> 'Bleu marine' ; couleur inconnue -> 1re lettre en maj."""
    if raw is None or not str(raw).strip():
        return None
    by_norm = {_norm_txt(c): c for c in _canonical_colors()}
    key = _norm_txt(raw)
    if key in by_norm:
        return by_norm[key]
    s = re.sub(r"\s+", " ", str(raw).strip())
    return s[0].upper() + s[1:].lower()


# ── Type (Excel) -> type objectif (barre 0->100) ─────────────────────────────
# Réutilise la table officielle objectif_mapping (source unique) : le Type
# Excel joue le rôle de sous-catégorie. Montres/bijoux/lunettes de vue n'ont
# volontairement PAS de type objectif (design actuel).

def resolve_type_objectif(type_excel: str | None, objectif_names: list[str]) -> str | None:
    from app.services.garderobe.objectif_mapping import derive_type_objectif
    return derive_type_objectif(None, type_excel, objectif_names)


# ── Type (Excel) -> catégorie de l'app (slots de tenue) ─────────────────────

_TYPE_TO_CATEGORIE_NORM: dict[str, str] = {
    "t shirt": "Haut", "t shirt manches longues": "Haut", "polo": "Haut",
    "chemise": "Shirt", "button up": "Shirt",
    "chino": "Pantalon", "jean": "Pantalon", "jean ballon": "Pantalon",
    "wide leg": "Pantalon", "jogging": "Pantalon", "trackpants": "Pantalon",
    "blouson": "Manteau", "bomber": "Manteau", "manteau": "Manteau",
    "coupe vent": "Manteau",
    "veste": "Veste", "veste sport": "Veste",
    "chelsea boots": "Chaussures", "bottes de neige": "Chaussures",
    "lunettes de soleil": "Yeux", "lunettes de vue": "Yeux",
    "smartwatch": "Montre", "montre analogique": "Montre",
    "montre automatique": "Montre",
    "bracelet": "Bijoux", "collier": "Cou",
}


def resolve_categorie(type_excel: str | None, dossier_pixel: str) -> str:
    """Catégorie app pour un Type Excel, repli sur le dossier du pixel art."""
    return _TYPE_TO_CATEGORIE_NORM.get(_norm_txt(type_excel), dossier_pixel)


# ── Lecture de l'Excel ───────────────────────────────────────────────────────

def parse_inventaire(path: Path) -> list[dict]:
    """Lignes remplies de la feuille 0, sous forme de dicts normalisés."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb.worksheets[0].iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return []
    hdr = [str(h).strip() if h is not None else "" for h in rows[0]]
    idx = {h: i for i, h in enumerate(hdr)}
    fixed = ["Marque", "Type", "Couleur", "Couleur Secondaire", "Motifs",
             "Photos Avant", "Photos Arriere", "Photos Pixelise", "Usure"]
    matiere_cols = [h for h in hdr if h and h not in fixed]

    def cell(row, name):
        i = idx.get(name)
        return row[i] if i is not None and i < len(row) else None

    out: list[dict] = []
    for row in rows[1:]:
        marque = cell(row, "Marque")
        if not marque or not str(marque).strip():
            continue  # ligne vide / pas encore remplie
        composition = {}
        for m in matiere_cols:
            v = cell(row, m)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = 0.0
            if v:
                composition[m] = v
        motifs_raw = cell(row, "Motifs")
        out.append({
            "marque": str(marque).strip(),
            "type": str(cell(row, "Type") or "").strip(),
            "couleur": normalize_couleur(cell(row, "Couleur")),
            "couleur_secondaire": normalize_couleur(cell(row, "Couleur Secondaire")),
            # 'TRUE' (texte) et True/False (booléen) coexistent dans le fichier
            "motifs": str(motifs_raw).strip().upper() in ("TRUE", "VRAI", "1", "OUI"),
            "photo_avant": str(cell(row, "Photos Avant") or "").strip() or None,
            "photo_arriere": str(cell(row, "Photos Arriere") or "").strip() or None,
            "pixel": str(cell(row, "Photos Pixelise") or "").strip() or None,
            "usure_pct": float(cell(row, "Usure") or 0.0),
            "composition": composition,
        })
    return out


# ── Pixel arts : nom de fichier cible ────────────────────────────────────────

_NUMBERED_RE = re.compile(r"^[A-Za-zÀ-ÿ]+\d+\.png$", re.IGNORECASE)


def target_asset_name(row: dict) -> str:
    """Nom cible du PNG : slug déjà nommé -> inchangé (la DB le référence),
    fichier numéroté (Veste01.png) -> <type>-<marque>-<couleur>.png."""
    pixel = row["pixel"] or ""
    if not _NUMBERED_RE.match(pixel):
        return pixel
    return build_slug(row["type"], row["marque"], row["couleur"]) + ".png"


def find_pixel_file(pixel_dir: Path, name: str) -> Path | None:
    """Retrouve un PNG par nom dans Pixelisé/*."""
    for p in pixel_dir.rglob("*.png"):
        if p.name == name:
            return p
    return None


# ── Import ───────────────────────────────────────────────────────────────────

def run_import(session: Session, dry_run: bool = False) -> dict:
    base = inventaire_dir()
    xlsx = base / "Vetements.xlsx"
    if not xlsx.exists():
        raise FileNotFoundError(str(xlsx))
    pixel_dir = base / "Pixelisé"
    normal_dir = base / "Normal"
    rows = parse_inventaire(xlsx)
    print(f"[import] {len(rows)} pièce(s) dans {xlsx}")

    stats = {"lignes": len(rows), "assets": 0, "maj": 0, "crees": 0,
             "photos": 0, "sans_pixel": 0}
    objectif_names = [t.nom for t in session.exec(select(ObjectifType)).all()]
    existing = list(session.exec(select(Vetement)).all())
    by_basename = {Path(v.image).name: v for v in existing if v.image}

    for row in rows:
        if not row["pixel"]:
            stats["sans_pixel"] += 1
            print(f"[import] (ignoré, pas de pixel art) {row['marque']} {row['type']}")
            continue
        src = find_pixel_file(pixel_dir, row["pixel"])
        if src is None:
            stats["sans_pixel"] += 1
            print(f"[import] ! PNG introuvable : {row['pixel']} "
                  f"({row['marque']} {row['type']})")
            continue
        categorie = resolve_categorie(row["type"], src.parent.name)
        asset_name = target_asset_name(row)
        image_rel = f"{categorie}/{asset_name}"

        # 1. copie du pixel art vers le dashboard
        dst = ASSETS_DIR / categorie / asset_name
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            print(f"[import] asset  {src.name} -> assets/{image_rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            stats["assets"] += 1

        # 2. upsert de la pièce
        v = by_basename.get(row["pixel"]) or by_basename.get(asset_name)
        slug = build_slug(row["type"], row["marque"], row["couleur"])
        if v is None:
            v = session.get(Vetement, slug)
        extra_updates = {
            "composition": row["composition"],
            "motifs": row["motifs"],
            "usure_pct": row["usure_pct"],
        }
        if row["couleur_secondaire"]:
            extra_updates["couleur_secondaire"] = row["couleur_secondaire"]

        type_obj = resolve_type_objectif(row["type"], objectif_names)

        if v is not None:
            # Pièce existante : champs curés (nom, couleur, catégorie...)
            # PRÉSERVÉS -- l'Excel n'est pas encore vérifié. On met à jour
            # image / extra / rattachement objectif.
            changes = []
            if v.image != image_rel:
                changes.append(f"image {v.image} -> {image_rel}")
                v.image = image_rel
            if v.type_objectif != type_obj:
                changes.append(f"objectif {v.type_objectif} -> {type_obj}")
                v.type_objectif = type_obj
            extra = dict(v.extra or {})
            extra.update(extra_updates)
            v.extra = extra
            if changes:
                print(f"[import] maj    {v.id} ({v.nom}) : {', '.join(changes)}")
            stats["maj"] += 1
        else:
            nom = " ".join(x for x in (row["marque"], row["type"], row["couleur"]) if x)
            v = Vetement(
                id=slug,
                nom=nom,
                marque=row["marque"],
                categorie=categorie,
                sous_categorie=row["type"],
                couleur=row["couleur"],
                matiere=", ".join(row["composition"]) or None,
                type_objectif=type_obj,
                image=image_rel,
                extra={**extra_updates, "a_verifier": True},
            )
            print(f"[import] crée   {slug} ({nom}) -> {image_rel}"
                  f"{f' [objectif: {type_obj}]' if type_obj else ''}")
            stats["crees"] += 1

        # 3. photos avant / arrière -> data/garderobe_photos
        extra = dict(v.extra or {})
        for role, key in (("avant", "photo_avant"), ("arriere", "photo_arriere")):
            fname = row[key]
            if not fname:
                continue
            src_photo = normal_dir / fname
            if not src_photo.exists():
                continue
            dst_name = f"{v.id}-{role}{src_photo.suffix.lower()}"
            dst_photo = photos_dir() / dst_name
            url = f"{MEDIA_URL_PREFIX}/{dst_name}"
            if extra.get(f"photo_{role}_url") != url or not dst_photo.exists():
                print(f"[import] photo  {fname} -> {dst_name}")
                if not dry_run:
                    dst_photo.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_photo, dst_photo)
                extra[f"photo_{role}_url"] = url
                stats["photos"] += 1
        extra.setdefault("photo_url", extra.get("photo_avant_url"))
        if extra.get("photo_url") is None:
            extra.pop("photo_url", None)
        v.extra = extra

        if not dry_run:
            session.add(v)
            by_basename[Path(v.image).name] = v

    if not dry_run:
        session.commit()

    print(f"[import] terminé : {stats['crees']} créée(s), {stats['maj']} mise(s) à jour, "
          f"{stats['assets']} asset(s) copié(s), {stats['photos']} photo(s), "
          f"{stats['sans_pixel']} ignorée(s).")
    return stats
