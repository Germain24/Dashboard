"""TDD — comparaison de prix Super C / Adonis pour la liste de courses.

Seule la logique pure (catégorisation, matching, règle de comparaison) est
testée ; le rafraîchissement (scrape navigateur) est best-effort, comme pour
adonis_pricing.py — voir _cache_age_seconds/refresh_if_stale, non testés ici.
"""
from __future__ import annotations

import json

from app.services.cuisine import store_pricing


def _fake_loader(data: dict[str, list[dict]]):
    def loader(store: str) -> list[dict]:
        return data.get(store, [])
    return loader


def test_pantry_uses_superc(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "555 Riz basmati", "price": 3.99}],
    }))
    rec = store_pricing.recommend_store("Riz basmati (sec)")
    assert rec == {"magasin": "Super C", "prix_estime": 3.99, "promo": False}


def test_viande_noble_now_uses_superc(monkeypatch):
    # viande_noble comparait Adonis seul (Super C = éviter, ancien design).
    # Désormais tout passe par Super C.
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Saumon atlantique", "price": 9.0}],
    }))
    rec = store_pricing.recommend_store("Saumon atlantique")
    assert rec == {"magasin": "Super C", "prix_estime": 9.0, "promo": False}


def test_viande_noble_no_recommendation_when_superc_has_no_match(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [],
    }))
    assert store_pricing.recommend_store("Saumon atlantique") is None


def test_fruits_legumes_uses_superc(monkeypatch):
    # L'exception "patate douce/oignon toujours Super C" est supprimée :
    # tout fruits_legumes passe par Super C de toute façon.
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Patate douce", "price": 5.0}],
    }))
    rec = store_pricing.recommend_store("Patate douce")
    assert rec == {"magasin": "Super C", "prix_estime": 5.0, "promo": False}


def test_fruits_legumes_banana_uses_superc(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Banane", "price": 0.31}],
    }))
    rec = store_pricing.recommend_store("Banane")
    assert rec == {"magasin": "Super C", "prix_estime": 0.31, "promo": False}


def test_superc_flyer_price_beats_regular_and_flags_promo(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Dinde hachée", "price": 6.0}],
        "superc_flyer": [{"name": "Dinde hachée", "price": 3.5}],
    }))
    rec = store_pricing.recommend_store("Dinde hachee")
    assert rec == {"magasin": "Super C", "prix_estime": 3.5, "promo": True}


def test_unclassified_ingredient_returns_none(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({}))
    assert store_pricing.recommend_store("Fromage cheddar") is None


def test_no_match_in_either_store_returns_none(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Something else", "price": 1.0}],
        "adonis": [],
    }))
    assert store_pricing.recommend_store("Riz basmati (sec)") is None


def test_apply_recommendations_annotates_without_mutating_input(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Basmati Rice", "price": 3.99}],
    }))
    items = [{"ingredient": "Riz basmati (sec)", "quantite": 500, "unite": "g", "rayon": "Épicerie"}]
    out = store_pricing.apply_recommendations(items)
    assert out[0]["magasin_recommande"] == "Super C"
    assert out[0]["prix_estime"] == 3.99
    assert out[0]["promo"] is False
    assert "magasin_recommande" not in items[0]   # ne mute pas l'original


def test_apply_recommendations_skips_item_on_error(monkeypatch):
    def boom(store: str) -> list[dict]:
        raise RuntimeError("cache corrompu")
    monkeypatch.setattr(store_pricing, "load_cached_items", boom)
    items = [{"ingredient": "Riz basmati (sec)", "quantite": 500, "unite": "g", "rayon": "Épicerie"}]
    out = store_pricing.apply_recommendations(items)
    assert "magasin_recommande" not in out[0]   # best-effort : pas de crash


# ── _current_week_search_terms / refresh_if_stale(terms) ─────────────────────

def test_search_terms_couvrent_le_catalogue_et_sont_dedupliques(monkeypatch):
    """Les termes viennent du CATALOGUE, pas de la liste de courses.

    Les dériver des courses avait un défaut fatal : sans plan de repas généré,
    la liste est vide, le scraper partait sans aucun terme et ne rafraîchissait
    rien — les prix restaient figés (14 jours constatés en production).
    """
    import pandas as pd

    from app.services.sante import aliments

    faux = pd.DataFrame(index=["Riz basmati (sec)", "Banane", "Fromage cheddar",
                               "Kefir", "Ingredient inexistant"])
    monkeypatch.setattr(aliments, "load_aliments_dataframe", lambda *a, **k: faux)

    terms = store_pricing._catalog_search_terms()

    assert "riz basmati" in terms and "banane" in terms
    assert "fromage cheddar" in terms      # naguère orphelin, donc jamais scrapé
    assert "kéfir" in terms
    assert len(terms) == len(set(terms))   # dédupliqué


def test_search_terms_vides_si_le_catalogue_est_illisible(monkeypatch):
    """Best-effort : le rafraîchissement au démarrage ne doit jamais lever."""
    from app.services.sante import aliments

    def boom(*a, **k):
        raise RuntimeError("catalogue illisible")

    monkeypatch.setattr(aliments, "load_aliments_dataframe", boom)
    assert store_pricing._catalog_search_terms() == []


def test_aliments_sportifs_passent_avant_le_reste_du_catalogue(monkeypatch):
    import pandas as pd

    from app.services.sante import aliments

    faux = pd.DataFrame(index=["Ingredient ordinaire", "Kefir", "Pates (sec)"])
    monkeypatch.setattr(aliments, "load_aliments_dataframe", lambda *a, **k: faux)
    monkeypatch.setattr(
        store_pricing.store_categories,
        "search_keywords",
        lambda name: {
            "Ingredient ordinaire": ["ordinaire"],
            "Kefir": ["kéfir", "kefir"],
            "Pates (sec)": ["pâtes alimentaires", "macaroni"],
        }[name],
    )

    terms = store_pricing._catalog_search_terms()
    assert terms[:2] == ["kéfir", "pâtes alimentaires"]
    assert terms.index("ordinaire") > terms.index("kefir")


def test_fromage_blanc_recherche_le_nom_quebecois():
    from app.services.cuisine import store_categories

    terms = store_categories.search_keywords("Fromage blanc")
    assert "fromage cottage" in terms
    assert "fromage frais" not in terms


def test_refresh_if_stale_uses_aisles_instead_of_individual_searches(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        class Result:
            returncode = 0
        return Result()

    # settings.data_dir.parent doit pointer vers un dossier contenant frontend/<script>
    (tmp_path / "frontend").mkdir(parents=True, exist_ok=True)
    (tmp_path / "frontend" / ".superc_scrape.mjs").write_text("// fake")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    class _FakeSettings:
        data_dir = tmp_path / "data"
        imports_dir = tmp_path / "data" / "imports"

    monkeypatch.setattr(store_pricing, "_cache_age_seconds", lambda store: float("inf"))
    monkeypatch.setattr(store_pricing.subprocess, "run", fake_run)
    monkeypatch.setattr(store_pricing, "settings", _FakeSettings())

    result = store_pricing.refresh_if_stale("superc", 1.0, terms=["basmati rice", "ground turkey"])
    assert result is True
    assert captured["cmd"][-1] == "--rayons"
    assert "basmati rice" not in captured["cmd"]


def test_refresh_all_if_stale_uses_no_search_terms(monkeypatch):
    calls = {}

    def fake_refresh_if_stale(store, max_age_h, terms=None):
        calls[store] = terms
        return True

    monkeypatch.setattr(store_pricing, "_current_week_search_terms", lambda: ["basmati rice"])
    monkeypatch.setattr(store_pricing, "refresh_if_stale", fake_refresh_if_stale)
    monkeypatch.setattr(store_pricing, "_rebuild_superc_reservoir", lambda _root: True)
    monkeypatch.setenv("STORE_PRICING_REFRESH", "1")

    store_pricing.refresh_all_if_stale()

    assert calls["superc"] is None
    assert calls["superc_flyer"] is None
    assert "lufa" not in calls


def test_cache_partiel_reste_perime_pour_permettre_la_reprise(monkeypatch, tmp_path):
    path = tmp_path / "data" / "imports" / "Cuisine" / "superc.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "items": [{"name": "Riz", "price": 2.0}],
        "refresh_complete": False,
        "completed_terms": ["riz"],
    }))

    class _FakeSettings:
        data_dir = tmp_path / "data"
        imports_dir = tmp_path / "data" / "imports"

    monkeypatch.setattr(store_pricing, "settings", _FakeSettings())
    assert store_pricing._cache_age_seconds("superc") == float("inf")


def test_ancien_cache_sans_marqueur_est_considere_incomplet(monkeypatch, tmp_path):
    path = tmp_path / "data" / "imports" / "Cuisine" / "superc.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"items": [{"name": "Riz", "price": 2.0}]}))

    class _FakeSettings:
        data_dir = tmp_path / "data"
        imports_dir = tmp_path / "data" / "imports"

    monkeypatch.setattr(store_pricing, "settings", _FakeSettings())
    assert store_pricing._cache_age_seconds("superc") == float("inf")
