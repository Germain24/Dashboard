"""Sous-routeur Garde-robe : historique, stats, fréquence, recommandations (#503)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session, select

from app.api.garderobe.common import vetement_to_dict, vetement_to_read
from app.api.garderobe.schemas import (
    CountEntry,
    RecommendationOut,
    StatsResponse,
    TenueHistoryOut,
    VetementRead,
)
from app.core.db import get_session
from app.core.pagination import Pagination, paginate
from app.models.garderobe import TenueHistory, Vetement
from app.services.garderobe import get_purchase_recommendations, is_worn_out, needs_wash
from app.services.garderobe.frequency import wear_buckets
from app.services.garderobe.style import get_color_category

router = APIRouter()


@router.get("/history", response_model=list[TenueHistoryOut])
def history(
    response: Response,
    limit: int = Query(20, ge=1, le=200),
    page: Pagination = Depends(),
    session: Session = Depends(get_session),
) -> list[TenueHistoryOut]:
    # `limit` historique conservé (rétro-compat) ; `offset` + X-Total-Count via paginate.
    stmt = select(TenueHistory).order_by(TenueHistory.date.desc())
    page.limit = min(limit, page.limit)
    rows = paginate(session, stmt, response, page)
    return [
        TenueHistoryOut(id=h.id, date=h.date, tenue=h.tenue, ids=h.ids, note=h.note)
        for h in rows
    ]


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    rows = session.exec(select(Vetement)).all()
    items = [vetement_to_dict(v) for v in rows]
    total = len(items)

    def _count(field: str) -> list[CountEntry]:
        counts: dict[str, int] = {}
        for it in items:
            v = it.get(field)
            if isinstance(v, list):
                for x in v:
                    if x:
                        counts[x] = counts.get(x, 0) + 1
            elif v:
                counts[v] = counts.get(v, 0) + 1
        return [
            CountEntry(label=label, count=count)
            for label, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

    # Ratio couleurs
    cats_count = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
    for it in items:
        cats_count[get_color_category(it.get("couleur"))] += 1
    denom = sum(cats_count.values()) or 1
    color_ratio = {k: v / denom for k, v in cats_count.items()}

    a_laver_rows = [vetement_to_read(v) for v in rows if needs_wash(vetement_to_dict(v))]
    hs_rows = [vetement_to_read(v) for v in rows if is_worn_out(vetement_to_dict(v))]

    # Valeur estimée : somme des prix renseignés dans extra.prix (#80)
    valeur = 0.0
    valeur_count = 0
    for it in items:
        prix = (it.get("extra") or {}).get("prix")
        if isinstance(prix, (int, float)) and prix > 0:
            valeur += float(prix)
            valeur_count += 1

    return StatsResponse(
        total=total,
        par_categorie=_count("categorie"),
        par_couleur=_count("couleur"),
        par_style=_count("style"),
        a_laver=a_laver_rows,
        hs=hs_rows,
        color_ratio=color_ratio,
        valeur_estimee=round(valeur, 2),
        valeur_count=valeur_count,
    )


@router.get("/frequence")
def frequence(top_n: int = Query(5, ge=1, le=20), session: Session = Depends(get_session)) -> dict:
    """Fréquence de port : jamais portées (à recycler), moins / plus portées (#77)."""
    rows = list(session.exec(select(Vetement)).all())
    by_id = {v.id: v for v in rows}
    buckets = wear_buckets([vetement_to_dict(v) for v in rows], top_n=top_n)

    def resolve(ids: list[str]) -> list[VetementRead]:
        return [vetement_to_read(by_id[i]) for i in ids if i in by_id]

    return {
        "total": buckets["total"],
        "never_worn_count": buckets["never_worn_count"],
        "never_worn": resolve(buckets["never_worn"]),
        "least_worn": resolve(buckets["least_worn"]),
        "most_worn": resolve(buckets["most_worn"]),
    }


@router.get("/recommendations", response_model=list[RecommendationOut])
def recommendations(session: Session = Depends(get_session)) -> list[RecommendationOut]:
    items = [vetement_to_dict(v) for v in session.exec(select(Vetement)).all()]
    recs = get_purchase_recommendations(items)
    return [RecommendationOut(**r) for r in recs]
