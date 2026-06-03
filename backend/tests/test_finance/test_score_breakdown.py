"""Détail du score Buffett par critère."""

from app.services.finance.buffett.scoring_pure import score_breakdown


def test_breakdown_pass_and_fail():
    ratios = {
        "gpm": 0.70,        # ≥ 0.60 -> ok
        "nim": 0.10,        # < 0.20 -> ko
        "roe": 0.25,        # ≥ 0.20 -> ok
        "debt_eq": 1.20,    # > 0.80 -> ko (trop endetté)
    }
    bd = {c["cle"]: c for c in score_breakdown(ratios)}

    assert bd["gpm"]["ok"] is True
    assert bd["gpm"]["categorie"] == "Marges"
    assert bd["nim"]["ok"] is False
    assert bd["roe"]["ok"] is True
    assert bd["debt_eq"]["ok"] is False
    # explication présente
    assert bd["roe"]["explication"]


def test_breakdown_skips_missing_or_nan():
    out = score_breakdown({"gpm": float("nan"), "roe": 0.3})
    cles = {c["cle"] for c in out}
    assert "gpm" not in cles  # NaN ignoré
    assert "roe" in cles


def test_breakdown_subscore_clamped():
    # gpm très élevé -> sous_score plafonné à 1.0
    out = {c["cle"]: c for c in score_breakdown({"gpm": 2.0})}
    assert out["gpm"]["sous_score"] == 1.0
