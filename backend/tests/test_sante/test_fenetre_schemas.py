import datetime as dt
from app.api.sante.schemas import (
    FenetreGenerateRequest, FenetreScore, ShoppingItem, WindowPlanResponse,
)


def test_schemas_construct():
    req = FenetreGenerateRequest(date=dt.date(2026, 7, 20))
    assert req.force is False
    resp = WindowPlanResponse(
        anchor_date=dt.date(2026, 7, 20), length=3, poids_used=51.0, jours=[],
        shopping_list=[ShoppingItem(aliment="Riz", quantite_g=900.0, prix=1.8, promo=True)],
        score=FenetreScore(couverture_moyenne=0.8, pct_micros_atteints=70.0,
                           cout_total=42.0, ratio=0.019, sous_couverts=["VitD"]),
        warning=None,
    )
    assert resp.shopping_list[0].promo is True
    assert resp.score.sous_couverts == ["VitD"]
