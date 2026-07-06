"""Catalogue crédit : chargement par défaut + surcharge JSON."""

import json

from app.services.finance.credit.catalog import CreditProduct, DEFAULT_CATALOG, load_catalog


def test_default_catalog_has_no_score_requirement_for_newcomer_products():
    newcomer = [p for p in DEFAULT_CATALOG if p.type == "programme_newcomer"]
    assert newcomer
    assert all(p.score_min_requis is None for p in newcomer)


def test_load_catalog_without_override_file_returns_default(tmp_path, monkeypatch):
    import app.services.finance.credit.catalog as catalog_mod
    monkeypatch.setattr(catalog_mod, "CATALOG_OVERRIDE_FILE", str(tmp_path / "missing.json"))
    result = load_catalog()
    assert result == DEFAULT_CATALOG


def test_load_catalog_with_override_file_replaces_default(tmp_path, monkeypatch):
    import app.services.finance.credit.catalog as catalog_mod
    override_path = tmp_path / "credit_catalog.json"
    override_path.write_text(json.dumps([
        {
            "institution": "Test Bank", "produit": "Carte Test", "type": "carte_standard",
            "limite_min": 100, "limite_max": 200, "anciennete_min_mois": 0,
            "score_min_requis": None, "anciennete_min_avant_1ere_hausse_mois": 6,
            "cooldown_hausse_mois": 6,
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(catalog_mod, "CATALOG_OVERRIDE_FILE", str(override_path))
    result = load_catalog()
    assert result == [CreditProduct(
        institution="Test Bank", produit="Carte Test", type="carte_standard",
        limite_min=100, limite_max=200, anciennete_min_mois=0,
        score_min_requis=None, anciennete_min_avant_1ere_hausse_mois=6,
        cooldown_hausse_mois=6,
    )]
