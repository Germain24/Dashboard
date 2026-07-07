"""TDD — comparaison de prix Super C / Adonis / Lufa pour la liste de courses.

Seule la logique pure (catégorisation, matching, règle de comparaison) est
testée ; le rafraîchissement (scrape navigateur) est best-effort, comme pour
adonis_pricing.py — voir _cache_age_seconds/refresh_if_stale, non testés ici.
"""
from __future__ import annotations

from app.services.cuisine import store_pricing


def _fake_loader(data: dict[str, list[dict]]):
    def loader(store: str) -> list[dict]:
        return data.get(store, [])
    return loader


def test_pantry_compares_superc_vs_adonis_cheapest_wins(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Basmati Rice", "price": 3.99}],
        "adonis": [{"name": "Basmati Rice", "price": 4.49}],
    }))
    rec = store_pricing.recommend_store("Riz basmati (sec)")
    assert rec == {"magasin": "Super C", "prix_estime": 3.99, "promo": False}


def test_viande_noble_excludes_superc_even_if_cheapest(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Atlantic Salmon", "price": 1.0}],   # jamais comparé pour cette catégorie
        "adonis": [{"name": "Atlantic Salmon", "price": 9.0}],
        "lufa": [{"name": "Atlantic Salmon", "price": 8.5}],
    }))
    rec = store_pricing.recommend_store("Saumon atlantique")
    assert rec == {"magasin": "Lufa", "prix_estime": 8.5, "promo": False}


def test_fruits_legumes_exception_items_always_superc_no_comparison(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Sweet Potato", "price": 5.0}],
        "adonis": [{"name": "Sweet Potato", "price": 0.5}],
        "lufa": [{"name": "Sweet Potato", "price": 0.4}],
    }))
    rec = store_pricing.recommend_store("Patate douce")
    assert rec == {"magasin": "Super C", "prix_estime": 5.0, "promo": False}


def test_superc_flyer_price_beats_regular_and_flags_promo(monkeypatch):
    monkeypatch.setattr(store_pricing, "load_cached_items", _fake_loader({
        "superc": [{"name": "Ground Turkey", "price": 6.0}],
        "superc_flyer": [{"name": "Ground Turkey", "price": 3.5}],
        "adonis": [{"name": "Ground Turkey", "price": 5.0}],
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
        "adonis": [{"name": "Basmati Rice", "price": 4.49}],
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

def test_current_week_search_terms_dedup_from_shopping_list(monkeypatch):
    from app.services.cuisine import shopping_list

    def fake_compute_shopping(session, semaine, jours=None, csv_path=None):
        return [
            {"ingredient": "Riz basmati (sec)"},
            {"ingredient": "Banane"},
            {"ingredient": "Fromage cheddar"},   # non classifié -> pas de mots-clés
        ]

    monkeypatch.setattr(shopping_list, "compute_shopping", fake_compute_shopping)
    terms = store_pricing._current_week_search_terms()
    assert terms == ["basmati rice", "banana"]


def test_current_week_search_terms_empty_on_error(monkeypatch):
    from app.services.cuisine import shopping_list

    def boom(session, semaine, jours=None, csv_path=None):
        raise RuntimeError("DB indisponible")

    monkeypatch.setattr(shopping_list, "compute_shopping", boom)
    assert store_pricing._current_week_search_terms() == []


def test_refresh_if_stale_passes_terms_to_subprocess(monkeypatch, tmp_path):
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
    assert "basmati rice" in captured["cmd"]
    assert "ground turkey" in captured["cmd"]


def test_refresh_all_if_stale_passes_none_terms_to_superc_flyer(monkeypatch):
    calls = {}

    def fake_refresh_if_stale(store, max_age_h, terms=None):
        calls[store] = terms
        return True

    monkeypatch.setattr(store_pricing, "_current_week_search_terms", lambda: ["basmati rice"])
    monkeypatch.setattr(store_pricing, "refresh_if_stale", fake_refresh_if_stale)
    monkeypatch.setenv("STORE_PRICING_REFRESH", "1")

    store_pricing.refresh_all_if_stale()

    assert calls["superc"] == ["basmati rice"]
    assert calls["lufa"] == ["basmati rice"]
    assert calls["superc_flyer"] is None
