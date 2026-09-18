"""Réapprovisionnement auto (#209) — surveille le stock skincare/compléments
et notifie quand un produit doit être racheté."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session

from app.models.scheduler import Notification
from app.models.skincare import SkincareProduct
from app.services.skincare.products import list_products


# ─── Fonctions pures ─────────────────────────────────────────────────────────

def days_of_stock_remaining(
    product: SkincareProduct,
    consommation_par_application: float = 1.0,
) -> Optional[float]:
    """Estime le nombre de jours de stock restant.

    Retourne None si stock_qte n'est pas renseigné.
    """
    if product.stock_qte is None:
        return None
    if product.stock_qte <= 0:
        return 0.0

    freq = product.frequence_type
    n = product.frequence_n or 1

    if freq == "quotidien":
        applications_per_day = 1.0
    elif freq == "n_par_semaine":
        applications_per_day = n / 7.0
    elif freq == "hebdo_jours":
        # frequence_jours = "0,3" → 2 jours/sem
        jours = product.frequence_jours or ""
        count = len([j for j in jours.split(",") if j.strip()])
        applications_per_day = max(count, 1) / 7.0
    else:
        applications_per_day = 1.0

    consommation_par_jour = applications_per_day * consommation_par_application
    if consommation_par_jour <= 0:
        return None
    return product.stock_qte / consommation_par_jour


def check_skincare_reorder(
    session: Session,
    today: Optional[dt.date] = None,
    seuil_jours: int = 14,
) -> list[dict]:
    """Retourne les produits actifs à racheter :
    - stock épuisé ou nul
    - périmé
    - estimation de jours restants < seuil_jours
    """
    today = today or dt.date.today()
    out: list[dict] = []
    for p in list_products(session, actifs_only=True):
        reason = None
        if p.stock_qte is not None and p.stock_qte <= 0:
            reason = "stock épuisé"
        elif p.date_peremption is not None and p.date_peremption < today:
            reason = "périmé"
        else:
            jours = days_of_stock_remaining(p)
            if jours is not None and jours < seuil_jours:
                reason = f"~{int(jours)}j restants"
        if reason:
            out.append({"id": p.id, "nom": p.nom, "raison": reason})
    return out


# ─── Intégration ─────────────────────────────────────────────────────────────

def run_skincare_reorder_check(
    session: Session,
    today: Optional[dt.date] = None,
) -> int:
    """Vérifie les produits skincare et crée une Notification si nécessaire."""
    products = check_skincare_reorder(session, today=today)
    if not products:
        return 0
    noms = ", ".join(p["nom"] for p in products)
    session.add(Notification(
        source="reapprovisionnement",
        level="warning",
        titre="Produits à racheter",
        message=f"{len(products)} produit(s) à renouveler : {noms}",
    ))
    session.commit()
    return len(products)
