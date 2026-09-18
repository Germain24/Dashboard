"""Purge des faux ETF du cache : entrées score>=200 dont le nom n'est PAS un fonds.

But : un titre mal classé ETF par l'ancien code (ex. cotation secondaire Boeing)
reste figé Score=200 dans cache_status.json et n'est jamais réanalysé. On purge
ces entrées (+ leur xlsx local) pour forcer une réanalyse propre, sans toucher aux
vrais ETF (iShares/UCITS), qui sont correctement classés.
"""

import json


def test_purge_removes_only_misclassified_etf(tmp_path):
    from app.services.finance.buffett.cache_manager import purge_misclassified_etf_cache

    cache_file = tmp_path / "cache_status.json"
    outdir = tmp_path / "fin"
    outdir.mkdir()
    cache = {
        "BA.TO": {"status": "success", "score": 200,
                  "metrics": {"Nom": "The Boeing Company"}},
        "IWDA.L": {"status": "success", "score": 200,
                   "metrics": {"Nom": "iShares Core MSCI World UCITS ETF"}},
        "AAPL": {"status": "success", "score": 85.0,
                 "metrics": {"Nom": "Apple Inc."}},
    }
    cache_file.write_text(json.dumps(cache))
    (outdir / "BA.TO.xlsx").write_text("x")    # faux ETF -> doit être supprimé
    (outdir / "IWDA.L.xlsx").write_text("x")   # vrai ETF  -> doit rester

    res = purge_misclassified_etf_cache(str(cache_file), str(outdir),
                                        etf_tickers={"IWDA.L"})

    assert res["removed"] == 1
    assert res["tickers"] == ["BA.TO"]
    assert res["files_deleted"] == 1

    new = json.loads(cache_file.read_text())
    assert "BA.TO" not in new            # faux ETF purgé
    assert "IWDA.L" in new               # vrai ETF conservé
    assert "AAPL" in new                 # action normale conservée
    assert not (outdir / "BA.TO.xlsx").exists()
    assert (outdir / "IWDA.L.xlsx").exists()


def test_purge_handles_missing_cache_file(tmp_path):
    from app.services.finance.buffett.cache_manager import purge_misclassified_etf_cache
    res = purge_misclassified_etf_cache(str(tmp_path / "nope.json"), str(tmp_path),
                                        etf_tickers=set())
    assert res["removed"] == 0
    assert res["tickers"] == []


def test_purge_ignores_non_etf_scores(tmp_path):
    from app.services.finance.buffett.cache_manager import purge_misclassified_etf_cache
    cache_file = tmp_path / "c.json"
    cache_file.write_text(json.dumps({
        "X": {"status": "success", "score": 199.0, "metrics": {"Nom": "Some Corp"}},
    }))
    res = purge_misclassified_etf_cache(str(cache_file), str(tmp_path), etf_tickers=set())
    assert res["removed"] == 0  # score < 200 -> pas un ETF, on n'y touche pas
