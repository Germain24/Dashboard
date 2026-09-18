"""Progression de lecture et estimation du temps restant (#144, #150)."""

from __future__ import annotations


def reading_progress(page_courante: int | None, pages: int | None) -> dict:
    """Pur : pourcentage de progression d'un livre.

    Renvoie page_courante/pages bornés à [0, total] et le pct arrondi.
    """
    total = pages or 0
    current = page_courante or 0
    if total <= 0:
        return {"page_courante": max(current, 0), "pages": total, "pct": 0}
    current = max(0, min(current, total))
    return {"page_courante": current, "pages": total, "pct": round(current / total * 100, 1)}


def reading_pace(total_pages_read: int, total_minutes: int) -> float:
    """Pur : rythme de lecture en pages/minute (0 si pas de données)."""
    if total_minutes <= 0 or total_pages_read <= 0:
        return 0.0
    return total_pages_read / total_minutes


def estimate_remaining_minutes(
    page_courante: int | None, pages: int | None, pace_pages_per_min: float
) -> int | None:
    """Pur : minutes estimées pour finir, selon le rythme.

    None si le rythme est inconnu ou le livre déjà terminé/sans pagination.
    """
    total = pages or 0
    current = page_courante or 0
    remaining = max(0, total - current)
    if total <= 0 or pace_pages_per_min <= 0 or remaining == 0:
        return None
    return round(remaining / pace_pages_per_min)
