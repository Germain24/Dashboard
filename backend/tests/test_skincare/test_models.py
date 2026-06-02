from app.models.skincare import SkincareProduct, SkincareLog


def test_skincare_product_defaults():
    p = SkincareProduct(nom="Sérum vitamine C", type="serum", moment="AM")
    assert p.ordre == 0
    assert p.frequence_type == "quotidien"
    assert p.actif is True
    assert p.cout == 0.0


def test_skincare_log_fields():
    log = SkincareLog(date_jour=__import__("datetime").date(2026, 6, 2), moment="PM", produits_ids="1,2,3")
    assert log.moment == "PM"
    assert log.produits_ids == "1,2,3"
