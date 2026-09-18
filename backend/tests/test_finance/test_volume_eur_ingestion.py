"""La colonne Volume produite par le scoring/ETF est en euros (spec
orchestration/a-faire/2026-07-15-volume-eur-design.md), pas en nb d'actions."""


def _rates(monkeypatch, table):
    from app.services.finance import fx
    monkeypatch.setattr(fx, "get_rate", lambda b, q, **k: table.get(b, 0.0))


def test_extract_metrics_volume_en_euros_usd(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("AAPL", {
        "currentPrice": 100.0, "volume": 1_000, "currency": "USD",
        "sector": "Technology", "country": "United States",
    })
    assert m["Volume"] == 90_000.0        # 1000 x 100 $ x 0.9
    assert m["Prix"] == 100.0             # prix inchangé (devise locale)


def test_extract_metrics_volume_eur_sans_conversion(monkeypatch):
    _rates(monkeypatch, {})               # aucun taux dispo : EUR n'en a pas besoin
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("AIR.PA", {"currentPrice": 150.0, "volume": 200,
                                   "currency": "EUR"})
    assert m["Volume"] == 30_000.0


def test_extract_metrics_taux_indispo_volume_zero(monkeypatch):
    _rates(monkeypatch, {})
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("7203.T", {"currentPrice": 2_000.0, "volume": 5_000,
                                   "currency": "JPY"})
    assert m["Volume"] == 0.0


def test_etf_result_defers_volume_to_group_download(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.runner import _etf_result
    score, metrics = _etf_result("SPY", {"info": {
        "longName": "SPDR S&P 500", "quoteType": "ETF",
        "regularMarketPrice": 500.0, "volume": 10_000, "currency": "USD",
    }})
    assert score == 0.0
    assert metrics["InstrumentType"] == "ETF"
    assert "Volume" not in metrics


# ── Marqueur d'unité + chemin "cache chaud" (#bug run 40 : le cache chaud
#    réémettait des volumes en nb d'actions d'avant la conversion, faussant
#    le filtre de liquidité sur quasi tout l'univers) ────────────────────────

def test_extract_metrics_pose_le_marqueur_et_etf_differe_le_volume(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.runner import _etf_result
    from app.services.finance.buffett.scoring import extract_metrics
    m = extract_metrics("AAPL", {"currentPrice": 100.0, "volume": 1_000,
                                 "currency": "USD"})
    assert m["VolumeDevise"] == "EUR"
    _, metrics = _etf_result("SPY", {"info": {"regularMarketPrice": 500.0,
                                              "volume": 10_000, "currency": "USD"}})
    assert "VolumeDevise" not in metrics


def test_ensure_volume_eur_convertit_les_metrics_historiques(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.currency import ensure_volume_eur
    legacy = {"Volume": 1_000, "Prix": 10.0, "Nom": "X"}
    out = ensure_volume_eur(legacy, "AAPL")
    assert out["Volume"] == 9_000.0
    assert out["VolumeDevise"] == "EUR"
    assert legacy["Volume"] == 1_000        # l'original n'est pas muté


def test_ensure_volume_eur_idempotent_sur_metrics_marquees(monkeypatch):
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett.currency import ensure_volume_eur
    deja = {"Volume": 9_000.0, "Prix": 10.0, "VolumeDevise": "EUR"}
    assert ensure_volume_eur(deja, "AAPL")["Volume"] == 9_000.0


def test_analyze_one_convertit_le_volume_du_cache_chaud(monkeypatch):
    import threading
    _rates(monkeypatch, {"USD": 0.9})
    from app.services.finance.buffett import runner

    class FakeCache:
        def get_cached_result(self, t):
            # entrée historique : volume brut, pas de marqueur
            return (95.0, {"Volume": 1_000, "Prix": 10.0, "Nom": "Apple"})

    results: dict = {}
    emitted: dict = {}
    ok = runner._analyze_one(
        "AAPL", results, FakeCache(), rate_limiter=None,
        deleted_tickers=set(), deleted_lock=threading.Lock(),
        on_result=lambda t, s, m: emitted.setdefault(t, (s, m)),
    )
    assert ok is True
    assert results["AAPL"][1]["Volume"] == 9_000.0
    assert results["AAPL"][1]["VolumeDevise"] == "EUR"
    assert emitted["AAPL"][1]["Volume"] == 9_000.0
